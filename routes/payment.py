# ---------------------------
# routes/payment.py
# ---------------------------

from __future__ import annotations  # ✅ TOUJOURS EN PREMIER

from datetime import datetime
import uuid
import logging
from typing import Any, Dict, Optional

from services.wallet.credit_service import CreditService
from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from services.account.card_service import CardService
from services.communication.email_service import EmailService
from services.core.idempotency_service import IdempotencyService
from services.order.order_service import OrderService
from services.stripe.stripe_service import StripeService
from services.reloadly.transaction_service import (
    TransactionServiceError,
    build_transaction_reference,
    get_existing_transaction,
    process_recharge,
    refresh_transaction_status,
)

payment_bp = Blueprint("payment", __name__, url_prefix="/payment")

logger = logging.getLogger(__name__)

# ---------------------------
# Helpers
# ---------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()

# ---------------------------
# Forfait display helper
# ---------------------------
def _get_forfait_display():
    forfait = session.get("recharge_forfait") or {}
    if isinstance(forfait, dict) and forfait.get("gb"):
        return str(forfait.get("gb"))
    return None

def _get_payment_context() -> Dict[str, Any]:
    phone = session.get("recharge_phone", "")

    base_amount = _safe_float(session.get("recharge_amount"), 0.0)
    recharge_total_amount = _safe_float(session.get("recharge_total_amount"), 0.0)

    # ---------------------------
    # Wallet credit
    # ---------------------------
    user_id = session.get("user_id")

    credit_available = 0.0
    if user_id:
        credit_available = _safe_float(
            CreditService.get_balance(user_id), 0.0
        )

    use_credit = bool(session.get("payment_use_credit", False))

    credit_used = min(credit_available, recharge_total_amount) if use_credit else 0.0

    final_amount = max(
        0.0,
        recharge_total_amount - credit_used
    )

    return {
        "phone": phone,
        "base_amount": base_amount,
        "recharge_amount": recharge_total_amount,
        "credit_available": credit_available,
        "use_credit": use_credit,
        "credit_used": credit_used,
        "final_amount": final_amount,
    }


def _get_or_create_payment_idempotency_key() -> str:
    idem_key = _safe_str(session.get("payment_idempotency_key"))

    if not idem_key:
        idem_key = str(uuid.uuid4())
        session["payment_idempotency_key"] = idem_key

    return idem_key


def _get_payment_intent_id() -> str:
    candidates = [
        session.get("last_payment_intent_id"),
        request.args.get("payment_intent"),
        request.args.get("payment_intent_id"),
        request.args.get("pi"),
    ]

    for value in candidates:
        value = _safe_str(value)
        if value:
            return value

    return ""


def _build_checkout_metadata(idem_key: str) -> Dict[str, str]:
    ctx = _get_payment_context()

    # ---------------------------
    # PROTECTION IDEMPOTENCY
    # ---------------------------
    current_amount = float(ctx["final_amount"])
    last_amount = session.get("last_payment_amount")

    # IMPORTANT : définir AVANT tout
    forfait = session.get("recharge_forfait")
    if not isinstance(forfait, dict):
        forfait = {}

    operator = session.get("recharge_operator")
    if not isinstance(operator, dict):
        operator = {}

    # reset si montant change
    if last_amount and float(last_amount) != current_amount:
        session.pop("payment_idempotency_key", None)

    session["last_payment_amount"] = current_amount

    return {
        "payment_idempotency_key": idem_key,
        "recharge_phone": _safe_str(ctx["phone"]),
        "base_amount": f"{ctx['base_amount']:.2f}",
        "recharge_amount": f"{ctx['recharge_amount']:.2f}",
        "charged_amount": f"{ctx['final_amount']:.2f}",
        "credit_used": f"{ctx['credit_used']:.2f}",
        "country_iso": _safe_str(session.get("country_iso")).upper(),
        "user_id": _safe_str(session.get("user_id")),
        "user_email": _safe_str(
            session.get("user_email") or session.get("pending_email")
        ),
        "forfait_id": _safe_str(forfait.get("id")),
        "operator_id": _safe_str(operator.get("id")),
        "operator_name": _safe_str(operator.get("name")),
        "operator_logo": _safe_str(operator.get("logo_url")),
    }


def _store_payment_success_payload(payload: Dict[str, Any]) -> None:
    session["payment_success_payload"] = payload

    transaction_id = payload.get("transaction_id")
    if transaction_id:
        session["last_transaction_id"] = transaction_id

    reference = payload.get("reference") or payload.get("transaction_reference")
    if reference:
        session["last_transaction_reference"] = reference


# ---------------------------
# Feature: Success Payload FIX FINAL
# ---------------------------

from datetime import datetime

def _build_success_payload(
    *,
    base_amount: float,
    charged_amount: float,
    credit_used: float,
    transaction_id: Optional[int],
    transaction_reference: str,
) -> Dict[str, Any]:

    payload_obj = OrderService.build_success_payload(amount=base_amount)

    ref = f"{transaction_id:012d}" if transaction_id else "000000000000"

    # ---------------------------
    # Taxes = total - montant
    # ---------------------------
    tax = round(charged_amount - base_amount, 2)

    payload_obj.update({
        "status": "SUCCESS",

        # UI values
        "amount": base_amount,
        "tax": tax,
        "total": charged_amount,

        # data
        "charged_amount": charged_amount,
        "credit_used": credit_used,
        "transaction_id": transaction_id,

        # reference
        "transaction_reference": ref,
        "reference": ref,

        # UI
        "date": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "order_number": ref,
    })

    return payload_obj


def _load_payload_from_payment_intent(payment_intent_id: str) -> Optional[Dict[str, Any]]:
    payment_intent_id = _safe_str(payment_intent_id)
    if not payment_intent_id:
        return None

    intent = StripeService.retrieve_payment(payment_intent_id)
    metadata = dict(getattr(intent, "metadata", {}) or {})

    idem_key = _safe_str(metadata.get("payment_idempotency_key"))
    if not idem_key:
        return None

    payload = IdempotencyService.get_result(idem_key)
    if payload:
        _store_payment_success_payload(payload)

    return payload


def _resolve_payment_status() -> Dict[str, Any]:
    payload = session.get("payment_success_payload")
    if isinstance(payload, dict) and payload:
        transaction_id = payload.get("transaction_id")
        reference = payload.get("transaction_reference")

        if transaction_id or reference:
            try:
                tx_result = refresh_transaction_status(
                    reference=reference or build_transaction_reference(
                        payment_reference=_safe_str(session.get("last_payment_intent_id")),
                        phone=_safe_str(session.get("recharge_phone")),
                        amount=_safe_float(session.get("recharge_amount"), None),
                        plan_id=(session.get("recharge_forfait") or {}).get("id"),
                        operator_id=(session.get("recharge_operator") or {}).get("id"),
                        country_iso=_safe_str(session.get("country_iso")),
                    ),
                    transaction_id=transaction_id,
                )

                payload["transaction_id"] = tx_result.transaction_id
                payload["reference"] = tx_result.transaction_id
                payload["transaction_reference"] = tx_result.custom_identifier
                session["payment_success_payload"] = payload
                session["last_transaction_id"] = tx_result.transaction_id
                session["last_transaction_reference"] = tx_result.custom_identifier

                if tx_result.status == "SUCCESS":
                    return {"status": "success"}
                if tx_result.status in {"FAILED", "REFUNDED"}:
                    return {"status": "failed"}

                return {"status": "processing"}

            except Exception:
                return {"status": "processing"}

        return {"status": "success"}

    payment_intent_id = _get_payment_intent_id()
    if not payment_intent_id:
        return {"status": "pending"}

    session["last_payment_intent_id"] = payment_intent_id

    try:
        intent = StripeService.retrieve_payment(payment_intent_id)
    except Exception:
        return {"status": "pending"}

    metadata = dict(getattr(intent, "metadata", {}) or {})
    stripe_status = _safe_str(getattr(intent, "status", ""))

    idem_key = _safe_str(metadata.get("payment_idempotency_key"))
    if not idem_key:
        return {"status": "pending"}

    existing = IdempotencyService.get_result(idem_key)
    if existing:
        _store_payment_success_payload(existing)

        tx_status = _safe_str(existing.get("status")).upper()
        if tx_status in {"FAILED", "REFUNDED"}:
            return {"status": "failed"}

        transaction_id = existing.get("transaction_id")
        reference = existing.get("transaction_reference")

        if transaction_id or reference:
            try:
                tx_result = refresh_transaction_status(
                    reference=reference,
                    transaction_id=transaction_id,
                )

                existing["transaction_id"] = tx_result.transaction_id
                existing["reference"] = tx_result.transaction_id
                existing["transaction_reference"] = tx_result.custom_identifier
                session["payment_success_payload"] = existing
                session["last_transaction_id"] = tx_result.transaction_id
                session["last_transaction_reference"] = tx_result.custom_identifier

                if tx_result.status == "SUCCESS":
                    return {"status": "success"}
                if tx_result.status in {"FAILED", "REFUNDED"}:
                    return {"status": "failed"}

                return {"status": "processing"}

            except Exception:
                return {"status": "processing"}

        return {"status": "success"}

    if stripe_status == "succeeded":
      return {"status": "success"}
        

    if stripe_status in {"canceled", "requires_payment_method"}:
        return {"status": "failed"}

    return {"status": "pending"}


# ---------------------------
# Payment method
# ---------------------------
@payment_bp.get("/card")
def card_get():

    # ---------------------------
    # Amount from shared link
    # ---------------------------
    amount_param = request.args.get("amount")

    if amount_param:
        try:
            amount = float(amount_param)

            session["recharge_amount"] = amount
            session["recharge_total_amount"] = amount

            # reset old recharge flow
            session.pop("recharge_phone", None)
            session.pop("recharge_forfait", None)
            session.pop("recharge_operator", None)
            session.pop("received_display", None)

            # optional UX flag
            session["payment_selected_method"] = "card"

        except Exception:
            pass

    # ---------------------------
    # EXISTING LOGIC (UNCHANGED)
    # ---------------------------
    if session.get("payment_selected_method") != "card":
        return redirect(url_for("payment.method_get"))

    ctx = _get_payment_context()
    amount = ctx.get("recharge_amount")

    if amount is None:
        return redirect(url_for("recharge.select_amount_get"))

    _get_or_create_payment_idempotency_key()

    # ---------------------------
    # FIX Reloadly quote
    # ---------------------------
    received_display = session.get("received_display")

    if not received_display:

        from services.reloadly.data_service import get_reloadly_quote
        from services.payment.currency_service import CurrencyService

        phone = session.get("recharge_phone")
        operator = session.get("recharge_operator") or {}
        country_iso = session.get("country_iso")
        operator_id = operator.get("id")

        quote = None
        if operator_id:
            quote = get_reloadly_quote(
                operator_id=operator_id,
                amount=ctx.get("base_amount"),
                phone=phone,
                country_iso=country_iso,
            )

        received_display = CurrencyService.received_display_value(
            phone=phone,
            amount=ctx.get("base_amount"),
            selected_forfait=session.get("recharge_forfait"),
            quote=quote
        )

    return render_template(
        "payment/card.html",
        phone=ctx["phone"],
        amount=amount,
        forfait_display=_get_forfait_display(),
        final_amount=ctx["final_amount"],
        credit_used=ctx.get("credit_used", 0),
        save_card=session.get("payment_save_card", True),
        cards=OrderService.get_saved_cards(session.get("user_id")),
        received_display=received_display
    )

# ---------------------------
# Payment method
# ---------------------------
@payment_bp.get("/method")
def method_get():

    # ---------------------------
    # LOGIN REQUIRED (WALLET SAFE)
    # ---------------------------
    if not session.get("user_id"):
        return redirect(url_for("auth.login", next=request.full_path))

    # ---------------------------
    # Amount from wallet link
    # ---------------------------
    amount_param = request.args.get("amount")

    if amount_param:
        try:
            amount = float(amount_param)

            session["recharge_amount"] = amount
            session["recharge_total_amount"] = amount

        except Exception:
            pass

    ctx = _get_payment_context()
    amount = ctx.get("recharge_amount")

    if amount is None:
        return redirect(url_for("recharge.select_amount_get"))

    # IMPORTANT ICI
    from_wallet = bool(request.args.get("amount"))

    # ---------------------------
    # FIX Reloadly quote
    # ---------------------------
    received_display = session.get("received_display")

    if not received_display:

        from services.reloadly.data_service import get_reloadly_quote
        from services.payment.currency_service import CurrencyService

        phone = session.get("recharge_phone")
        operator = session.get("recharge_operator") or {}
        country_iso = session.get("country_iso")
        operator_id = operator.get("id")

        quote = None
        if operator_id:
            quote = get_reloadly_quote(
                operator_id=operator_id,
                amount=ctx.get("base_amount"),
                phone=phone,
                country_iso=country_iso,
            )

        received_display = CurrencyService.received_display_value(
            phone=phone,
            amount=ctx.get("base_amount"),
            selected_forfait=session.get("recharge_forfait"),
            quote=quote
        )

# ---------------------------
# LIVE CURRENCY DISPLAY
# ---------------------------
    from services.payment.currency_service import CurrencyService

    country_iso = session.get("country_iso")

    currency = CurrencyService.currency_from_country(country_iso)

    converted_amount = CurrencyService.convert_live(
    ctx["final_amount"],
    currency
)

    return render_template(
        "payment/method.html",
        phone=ctx["phone"],
        amount=amount,
        forfait_display=_get_forfait_display(),
        credit_available=ctx["credit_available"],
        use_credit=ctx["use_credit"],
        credit_used=ctx["credit_used"],
        final_amount=ctx["final_amount"],
        selected_method=session.get("payment_selected_method", "card"),
        save_card=session.get("payment_save_card", True),
        is_forfait_minutes=False,
        received_display=received_display,
        from_wallet=from_wallet,
        currency=currency,
        converted_amount=converted_amount
    )

@payment_bp.post("/method")
def method_post():
    selected_method = request.form.get("selected_method", "card")
    save_card = request.form.get("save_card") == "1"
    use_credit = request.form.get("use_credit") == "1"

    session["payment_selected_method"] = selected_method
    session["payment_save_card"] = save_card
    session["payment_use_credit"] = use_credit

    if selected_method != "card":
        session["payment_toast"] = "payment.methodUnavailable"
        return redirect(url_for("payment.method_get"))

    return redirect(url_for("payment.card_get"))


# ---------------------------
# Process card payment
# ---------------------------
@payment_bp.post("/card")
def card_post():

    if session.get("payment_selected_method") != "card":
        return redirect(url_for("payment.method_get"))

    ctx = _get_payment_context()

    if not ctx["recharge_amount"]:
        return redirect(url_for("recharge.select_amount_get"))

    idem_key = _get_or_create_payment_idempotency_key()

    existing = IdempotencyService.get_result(idem_key)
    if existing:
        _store_payment_success_payload(existing)
        return jsonify({"success": True, "already_processed": True})

    metadata = _build_checkout_metadata(idem_key)
    print("PAYMENT METADATA DEBUG:", metadata)
    try:
        intent = StripeService.create_payment_intent(
            amount=ctx["final_amount"],
            currency="eur",
            metadata=metadata,
        )

        session["last_payment_intent_id"] = intent.id

        return jsonify({
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
        })

    except Exception as exc:
        print("Stripe payment intent error:", exc)
        return jsonify({"error": "payment_error"}), 400


# ---------------------------
# Stripe webhook
# ---------------------------
@payment_bp.post("/webhook")
def stripe_webhook_post():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = StripeService.construct_webhook_event(payload, sig_header)
    except Exception as exc:
        print("❌ Stripe webhook signature error:", exc)
        return jsonify({"ok": False}), 400

    event_type = event.get("type")
    event_data = (event.get("data") or {}).get("object") or {}

    if event_type != "payment_intent.succeeded":
        return jsonify({"ok": True}), 200

    stripe_status = _safe_str(event_data.get("status"))
    if stripe_status != "succeeded":
        return jsonify({"ok": True}), 200

    metadata = event_data.get("metadata", {}) or {}
    idem_key = _safe_str(metadata.get("payment_idempotency_key"))

    if not idem_key:
        return jsonify({"ok": False, "error": "missing_idempotency_key"}), 400

    # ---------------------------
    # Idempotency check (APRES validation Stripe)
    # ---------------------------
    existing = IdempotencyService.get_result(idem_key)
    if existing:
        return jsonify({"ok": True, "deduplicated": True}), 200

    # ---------------------------
    # Hard deduplication (transaction level)
    # ---------------------------
    payment_reference = _safe_str(event_data.get("id"))
    session["last_payment_intent_id"] = payment_reference

    existing_tx = get_existing_transaction(payment_reference)
    if existing_tx:
        logger.warning("⚠️ Duplicate recharge prevented (existing transaction)")
        return jsonify({"ok": True, "deduplicated": True}), 200

    stripe_status = _safe_str(event_data.get("status"))
    if stripe_status != "succeeded":
        return jsonify({"ok": True}), 200

    phone = _safe_str(metadata.get("recharge_phone"))
    country_iso = _safe_str(metadata.get("country_iso")).upper()
    forfait_id_raw = _safe_str(metadata.get("forfait_id"))
    operator_id_raw = _safe_str(metadata.get("operator_id"))
    operator_name = _safe_str(metadata.get("operator_name"))
    operator_logo = _safe_str(metadata.get("operator_logo"))

    user_email = _safe_str(metadata.get("user_email"))
    user_id = _safe_str(metadata.get("user_id"))

    base_amount = _safe_float(metadata.get("base_amount"), 0.0)
    charged_amount = _safe_float(metadata.get("charged_amount"), 0.0)
    credit_used = _safe_float(metadata.get("credit_used"), 0.0)

    if not phone or base_amount <= 0:
        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "invalid_metadata"},
        )
        return jsonify({"ok": True}), 200

    stripe_amount_received = _safe_float(event_data.get("amount_received"), 0.0) / 100.0
    stripe_currency = _safe_str(event_data.get("currency")).lower()

    if stripe_currency != "eur":
        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "invalid_currency"},
        )
        return jsonify({"ok": True}), 200

    if abs(stripe_amount_received - charged_amount) > 0.01:
        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "amount_mismatch"},
        )
        return jsonify({"ok": True}), 200

    try:
        print("FORFAIT DEBUG:", forfait_id_raw)
        result = process_recharge(
            payment_reference=payment_reference,
            phone=phone,
            country_iso=country_iso,
            amount=None if forfait_id_raw else round(base_amount, 2),
            plan_id=int(forfait_id_raw) if forfait_id_raw else None,
            operator_id=int(operator_id_raw) if operator_id_raw else None,
            user_id=user_id or session.get("user_id"),
            metadata={
                "flow": "stripe_webhook",
                "payment_intent_id": payment_reference,
                "payment_idempotency_key": idem_key,
            },
        )

        payload_obj = _build_success_payload(
            base_amount=base_amount,
            charged_amount=charged_amount,
              credit_used=credit_used,
            transaction_id=result.transaction_id,
            transaction_reference=result.custom_identifier,
       )

        CreditService.add_credit(
          user_id=user_id,
         amount=charged_amount
       )
        
        # ---------------------------
        # Refresh wallet session
        # ---------------------------
        try:
            new_balance = CreditService.get_balance(user_id)
            session["user_balance"] = new_balance
        except Exception:
            pass

        if result.status in {"FAILED", "REFUNDED"}:
            payload_obj["status"] = "FAILED"
            payload_obj["reason"] = "recharge_failed"

        IdempotencyService.store_result(idem_key, payload_obj)
        _store_payment_success_payload(payload_obj)

        # ---------------------------
        # Email success
        # ---------------------------
        # ---------------------------
# Email success (ONLY when reloadly success)
# ---------------------------
        if user_email and result.status == "SUCCESS":
            try:
                EmailService.send_payment_success(
                    email=user_email,
                    payload=payload_obj,
                    phone=phone,
                    country_name=country_iso,
                    operator_name=operator_name,
                    operator_logo=operator_logo,
                )
            except Exception as email_error:
                print("❌ Email error:", email_error)

    except TransactionServiceError as process_error:
        print("❌ Recharge processing error:", process_error)

        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "recharge_error"},
        )

        return jsonify({"ok": True}), 200

    except Exception as process_error:
        print("❌ Webhook processing error:", process_error)

        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "unexpected_webhook_error"},
        )

        return jsonify({"ok": True}), 200

    return jsonify({"ok": True}), 200


# ---------------------------
# Payment status
# ---------------------------
@payment_bp.get("/status")
def payment_status():
    status = _resolve_payment_status()
    return jsonify(status)


# ---------------------------
# Payment success page
# ---------------------------
@payment_bp.get("/success")
def payment_success():

    payment_intent_id = _get_payment_intent_id()

    if payment_intent_id:
        session["last_payment_intent_id"] = payment_intent_id
        _load_payload_from_payment_intent(payment_intent_id)

    payload = session.get("payment_success_payload") or {}

    received_display = session.get("received_display")
    forfait_display = _get_forfait_display()

    # ---------------------------
    # Cas 1 : pas encore de payload
    # ---------------------------
    if not payload:
        ctx = _get_payment_context()

        return render_template(
            "payment/success.html",
            status="processing",
            amount=ctx["recharge_amount"],
            date=None,
            order_number="...",
            reference="...",
            forfait_display=forfait_display,
            received_display=received_display,
        )

    # ---------------------------
    # Cas 2 : payload final
    # ---------------------------
    return render_template(
        "payment/success.html",
        status="success" if _safe_str(payload.get("status"), "SUCCESS") != "FAILED" else "failed",
        amount=payload.get("amount"),
        date=payload.get("date"),
        order_number=payload.get("order_number"),
        reference=payload.get("transaction_reference") or payload.get("reference"),
        forfait_display=forfait_display,
        received_display=received_display,
    )

    # ---------------------------
    # Cas 2 : payload dispo → affichage final
    # ---------------------------
    return render_template(
    "payment/success.html",
    status="success" if _safe_str(payload.get("status"), "SUCCESS") != "FAILED" else "failed",
    amount=payload.get("amount"),
    forfait_display=_get_forfait_display(),
    date=payload.get("date"),
    order_number=payload.get("order_number"),
    reference=payload.get("transaction_reference") or payload.get("reference"),
)


# ---------------------------
# Payment success finish
# ---------------------------
@payment_bp.post("/success/finish")
def success_finish_post():
    session.pop("payment_success_payload", None)
    session.pop("payment_idempotency_key", None)
    session.pop("payment_toast", None)
    session.pop("payment_selected_method", None)
    session.pop("payment_save_card", None)
    session.pop("payment_use_credit", None)
    session.pop("last_payment_intent_id", None)

    session.pop("recharge_phone", None)
    session.pop("recharge_amount", None)
    session.pop("recharge_total_amount", None)
    session.pop("recharge_forfait", None)
    session.pop("recharge_operator", None)
    session.pop("country_iso", None)

    return redirect(url_for("recharge.enter_number_get"))