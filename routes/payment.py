# ---------------------------
# routes/payment.py
# ---------------------------

from __future__ import annotations  # ✅ TOUJOURS EN PREMIER

from datetime import datetime, timezone
import uuid
import logging
import hmac
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from services.account.card_service import CardService
from services.communication.email_service import EmailService
from services.core.idempotency_service import IdempotencyService
from services.order.order_service import OrderService
from services.order.order_reference_service import OrderReferenceService
from services.stripe.stripe_service import StripeService
from services.payment.currency_service import CurrencyService
from services.payment.fees_service import FeesService
from services.reloadly.transaction_service import (
    TransactionServiceError,
    InvalidTransactionInputError,
    build_transaction_reference,
    get_existing_transaction,
    process_recharge,
    refresh_transaction_status,
)
from services.security.payment_guard_service import (
    PaymentGuardError,
    PaymentGuardService,
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
def _safe_get(
    obj: Any,
    key: str,
    default: Any = None,
) -> Any:

    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)
# ---------------------------
# Forfait display helper
# ---------------------------
def _get_forfait_display():
    forfait = session.get("recharge_forfait") or {}
    if isinstance(forfait, dict) and forfait.get("gb"):
        return str(forfait.get("gb"))
    return None


# ---------------------------
# Payment context (SOURCE UNIQUE FEES)
# ---------------------------
def _get_payment_context() -> Dict[str, Any]:

    phone = session.get(
        "recharge_phone",
        ""
    )

    forfait = session.get(
        "recharge_forfait"
    ) or {}

    # ---------------------------
    # Base amount
    # ---------------------------
    base_amount = 0.0

    if (
        isinstance(forfait, dict)
        and forfait
    ):

        raw_amount = (
            forfait.get("price")
            or forfait.get("amount")
            or forfait.get("value")
        )

        base_amount = _safe_float(
            raw_amount,
            0.0,
        )

    if base_amount <= 0:

        base_amount = _safe_float(
            session.get("recharge_amount"),
            0.0,
        )

    if base_amount < 0:
        base_amount = 0.0

    # ---------------------------
    # Invalid amount protection
    # ---------------------------
    if base_amount <= 0:

        logger.warning(
            "Invalid payment amount | session=%s",
            dict(session),
        )

        return {
            "phone": phone,
            "base_amount": 0.0,
            "recharge_amount": 0.0,
            "final_amount": 0.0,
            "tax_rate": 0.0,
            "tax": 0.0,
        }

    # ---------------------------
    # Fees source unique
    # ---------------------------
    currency = CurrencyService.currency_from_phone(
        phone
    )

    breakdown = FeesService.breakdown(
        base_amount,
        currency,
    )

    # ---------------------------
    # Sync session
    # ---------------------------
    session["recharge_amount"] = float(
        breakdown["amount"]
    )

    session["tax_rate"] = float(
        breakdown["tax_rate"]
    )

    session["recharge_fee"] = float(
        breakdown["tax"]
    )

    session["recharge_total_amount"] = float(
        breakdown["total"]
    )

    session.modified = True

    # ---------------------------
    # Final payload
    # ---------------------------
    return {
        "phone": phone,

        "base_amount": float(
            breakdown["amount"]
        ),

        "recharge_amount": float(
            breakdown["total"]
        ),

        "final_amount": float(
            breakdown["total"]
        ),

        "tax_rate": float(
            breakdown["tax_rate"]
        ),

        "tax": float(
            breakdown["tax"]
        ),
    }


def _get_or_create_payment_idempotency_key() -> str:
    idem_key = _safe_str(session.get("payment_idempotency_key"))

    if not idem_key:
        idem_key = str(uuid.uuid4())
        session["payment_idempotency_key"] = idem_key

    return idem_key


# ---------------------------
# Customer order reference
# ---------------------------
def _get_or_create_order_reference() -> str:

    order_ref = _safe_str(
        session.get("payment_order_reference")
    )

    if order_ref:
        return order_ref

    try:
        order_ref = OrderReferenceService.generate_order_reference()

    except Exception:
        logger.exception(
            "Order reference generation error"
        )

        order_ref = uuid.uuid4().hex[:9].upper()

    session["payment_order_reference"] = order_ref
    session["last_order_reference"] = order_ref

    return order_ref


# ---------------------------
# Payment form nonce
# ---------------------------

def _ensure_payment_form_nonce() -> str:

    nonce = _safe_str(
        session.get("payment_form_nonce")
    )

    if not nonce:
        nonce = uuid.uuid4().hex
        session["payment_form_nonce"] = nonce

    return nonce


def _validate_payment_form_nonce(data: Dict[str, Any]) -> bool:

    expected = _safe_str(
        session.get("payment_form_nonce")
    )

    received = _safe_str(
        (data or {}).get("payment_form_nonce")
        or request.headers.get("X-Yeslek-Payment-Nonce")
    )

    if not expected or not received:
        return False

    return hmac.compare_digest(
        expected,
        received,
    )

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
    # Idempotency amount sync
    # ---------------------------
    current_amount = float(
        ctx["final_amount"]
    )

    last_amount = session.get(
        "last_payment_amount"
    )

    if last_amount and float(last_amount) != current_amount:
        idem_key = str(uuid.uuid4())
        session["payment_idempotency_key"] = idem_key

    session["last_payment_amount"] = current_amount

    # ---------------------------
    # Safe session objects
    # ---------------------------
    forfait = session.get("recharge_forfait")

    if not isinstance(forfait, dict):
        forfait = {}

    operator = session.get("recharge_operator")

    if not isinstance(operator, dict):
        operator = {}

    # ---------------------------
    # Customer reference
    # ---------------------------
    order_ref = _get_or_create_order_reference()

    # ---------------------------
    # Payment language
    # ---------------------------
    payment_lang = _safe_str(
        session.get("lang")
        or request.cookies.get("lang")
        or request.args.get("lang")
        or "en"
    ).lower()

    if payment_lang not in {
        "fr",
        "en",
        "ar",
        "fa",
        "ps",
        "uz",
        "tr",
        "de",
    }:
        payment_lang = "en"

    # ---------------------------
    # Metadata
    # ---------------------------
    return {
        "payment_idempotency_key": idem_key,
        "lang": payment_lang,
        "locale": payment_lang,
        "order_reference": order_ref,
        "order_number": order_ref,
        "recharge_phone": _safe_str(ctx["phone"]),
        "base_amount": f"{ctx['base_amount']:.2f}",
        "recharge_amount": f"{ctx['recharge_amount']:.2f}",
        "charged_amount": f"{ctx['final_amount']:.2f}",
        "country_iso": _safe_str(session.get("country_iso")).upper(),
        "user_id": _safe_str(session.get("user_id")),
        "user_email": _safe_str(
            session.get("user_email")
            or session.get("pending_email")
        ),
        "forfait_id": _safe_str(
            forfait.get("id")
            or forfait.get("name")
        ),
        "operator_id": _safe_str(
            operator.get("id")
        ),
        "operator_name": _safe_str(
            operator.get("name")
        ),
        "operator_logo": _safe_str(
            operator.get("logo_url")
        ),
        "save_card": str(
            session.get("payment_save_card", True)
        ).lower(),
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
# Feature: Success Payload (PRO VERSION)
# ---------------------------

def _build_success_payload(
    *,
    base_amount: float,
    charged_amount: float,
    transaction_id: Optional[int],
    transaction_reference: str,
    order_reference: Optional[str] = None,
) -> Dict[str, Any]:

    # ---------------------------
    # Base payload (core)
    # ---------------------------
    payload_obj = OrderService.build_success_payload(amount=base_amount)

    # ---------------------------
    # Safe session data
    # ---------------------------
    forfait = session.get("recharge_forfait") or {}
    operator = session.get("recharge_operator") or {}

    # ---------------------------
    # Customer order reference
    # ---------------------------
    order_ref = (
        _safe_str(order_reference)
        or _safe_str(session.get("payment_order_reference"))
    )

    if not order_ref:

        try:
            order_ref = OrderReferenceService.generate_order_reference()

        except Exception:
            logger.exception(
                "Order reference generation error"
            )

            order_ref = (
                f"{int(transaction_id):09d}"
                if transaction_id
                else uuid.uuid4().hex[:9].upper()
            )

    session["payment_order_reference"] = order_ref
    session["last_order_reference"] = order_ref

    # ---------------------------
    # Reloadly transaction reference
    # ---------------------------
    reloadly_ref = _safe_str(
        transaction_reference
    )
    # ---------------------------
    # Taxes
    # ---------------------------
    tax = round(charged_amount - base_amount, 2)

    # ---------------------------
    # Forfait display (UX)
    # ---------------------------
    forfait_display = None

    if isinstance(forfait, dict):
        gb = forfait.get("gb")
        validity = forfait.get("validity")
        name = forfait.get("name")

        if gb and validity:
            forfait_display = f"{gb} • {validity}"
        elif gb:
            forfait_display = gb
        elif name:
            forfait_display = name

    # fallback airtime
    if not forfait_display:
        forfait_display = "Recharge mobile"

    # ---------------------------
    # Payload final
    # ---------------------------
    payload_obj.update({

        # ---------------------------
        # Status
        # ---------------------------
        "status": "SUCCESS",

        # ---------------------------
        # UI values
        # ---------------------------
        "amount": round(base_amount, 2),
        "tax": tax,
        "total": round(charged_amount, 2),

        # ---------------------------
        # Product (🔥 FIX IMPORTANT)
        # ---------------------------
        "forfait": forfait_display,

        # ---------------------------
        # Operator (future UI/email)
        # ---------------------------
        "operator_name": operator.get("name"),
        "operator_logo": operator.get("logo_url"),

        # ---------------------------
        # Data
        # ---------------------------
        "charged_amount": round(charged_amount, 2),
        "transaction_id": transaction_id,

        # ---------------------------
        # Customer reference
        # ---------------------------
        "reference": order_ref,
        "order_number": order_ref,

        # ---------------------------
        # Reloadly internal reference
        # ---------------------------
        "transaction_reference": reloadly_ref,
        "reloadly_reference": reloadly_ref,
        # ---------------------------
        # Meta
        # ---------------------------
         "date_iso": datetime.now(timezone.utc).isoformat(),
        "phone": session.get("recharge_phone"),
        "country_iso": session.get("country_iso"),

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


# ---------------------------
# Resolve payment status
# ---------------------------
def _resolve_payment_status() -> Dict[str, Any]:

    payload = session.get(
        "payment_success_payload"
    )

    # ---------------------------
    # Existing session payload
    # ---------------------------
    if isinstance(payload, dict) and payload:

        transaction_id = payload.get(
            "transaction_id"
        )

        reference = payload.get(
            "transaction_reference"
        )

        # ---------------------------
        # Sync Reloadly status
        # ---------------------------
        if transaction_id or reference:

            try:

                tx_result = refresh_transaction_status(
                    reference=reference or build_transaction_reference(
                        payment_reference=_safe_str(
                            session.get(
                                "last_payment_intent_id"
                            )
                        ),
                        phone=_safe_str(
                            session.get(
                                "recharge_phone"
                            )
                        ),
                        amount=_safe_float(
                            session.get(
                                "recharge_amount"
                            ),
                            None,
                        ),
                        plan_id=(
                            session.get(
                                "recharge_forfait"
                            ) or {}
                        ).get("id"),
                        operator_id=(
                            session.get(
                                "recharge_operator"
                            ) or {}
                        ).get("id"),
                        country_iso=_safe_str(
                            session.get(
                                "country_iso"
                            )
                        ),
                    ),
                    transaction_id=transaction_id,
                )

                payload["transaction_id"] = (
                    tx_result.transaction_id
                )

                payload["transaction_reference"] = (
                    tx_result.custom_identifier
                    or payload.get(
                        "transaction_reference"
                    )
                )

                payload["reloadly_reference"] = (
                    tx_result.custom_identifier
                    or payload.get(
                        "reloadly_reference"
                    )
                )
                session[
                    "payment_success_payload"
                ] = payload

                session[
                    "last_transaction_id"
                ] = tx_result.transaction_id

                session[
                    "last_transaction_reference"
                ] = tx_result.custom_identifier

                # ---------------------------
                # SUCCESS
                # ---------------------------
                if tx_result.status == "SUCCESS":

                    return {
                        "status": "success"
                    }

                # ---------------------------
                # FAILED
                # ---------------------------
                if tx_result.status in {
                    "FAILED",
                    "REFUNDED",
                }:

                    return {
                        "status": "failed"
                    }

                # ---------------------------
                # PROCESSING
                # ---------------------------
                return {
                    "status": "processing"
                }

            # ---------------------------
            # Reloadly transaction
            # not created yet
            # ---------------------------
            except InvalidTransactionInputError:

                logger.warning(
                    "Reloadly transaction not found yet"
                )

                return {
                    "status": "processing"
                }

            # ---------------------------
            # Unexpected error
            # ---------------------------
            except Exception:

                logger.exception(
                    "Payment status refresh error"
                )

                return {
                    "status": "processing"
                }

        # ---------------------------
        # Existing payload fallback
        # ---------------------------
        return {
            "status": "success"
        }

    # ---------------------------
    # Stripe payment intent
    # ---------------------------
    payment_intent_id = _get_payment_intent_id()

    if not payment_intent_id:

        return {
            "status": "pending"
        }

    session[
        "last_payment_intent_id"
    ] = payment_intent_id

    # ---------------------------
    # Retrieve Stripe intent
    # ---------------------------
    try:

        intent = StripeService.retrieve_payment(
            payment_intent_id
        )

    except Exception:

        logger.exception(
            "Stripe retrieve payment error"
        )

        return {
            "status": "pending"
        }

    metadata = dict(
        getattr(intent, "metadata", {}) or {}
    )

    stripe_status = _safe_str(
        getattr(intent, "status", "")
    ).lower()

    idem_key = _safe_str(
        metadata.get(
            "payment_idempotency_key"
        )
    )

    if not idem_key:

        return {
            "status": "pending"
        }

    # ---------------------------
    # Existing idempotent result
    # ---------------------------
    existing = IdempotencyService.get_result(
        idem_key
    )

    if existing:

        _store_payment_success_payload(
            existing
        )

        tx_status = _safe_str(
            existing.get("status")
        ).upper()

        # ---------------------------
        # SUCCESS
        # ---------------------------
        if tx_status == "SUCCESS":

            return {
                "status": "success"
            }

        # ---------------------------
        # FAILED
        # ---------------------------
        if tx_status in {
            "FAILED",
            "REFUNDED",
        }:

            return {
                "status": "failed"
            }

        # ---------------------------
        # PROCESSING
        # ---------------------------
        return {
            "status": "processing"
        }

    # ---------------------------
    # Stripe success fallback
    # Stripe paid but webhook
    # still processing
    # ---------------------------
    if stripe_status == "succeeded":

        return {
            "status": "processing"
        }

    # ---------------------------
    # Failed Stripe states
    # ---------------------------
    if stripe_status in {
        "canceled",
        "requires_payment_method",
        "payment_failed",
    }:

        return {
            "status": "failed"
        }

    # ---------------------------
    # Default pending
    # ---------------------------
    return {
        "status": "pending"
    }



# ---------------------------
# Card payment page
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
            session["payment_selected_method"] = "card"

            session.pop("recharge_phone", None)
            session.pop("recharge_forfait", None)
            session.pop("recharge_operator", None)
            session.pop("received_display", None)

        except Exception:
            pass

    # ---------------------------
    # Default payment method
    # ---------------------------
    if not session.get("payment_selected_method"):
        session["payment_selected_method"] = "card"

    if session.get("payment_selected_method") != "card":
        return redirect(
            url_for("payment.method_get")
        )

    # ---------------------------
    # Require amount
    # ---------------------------
    if (
        not session.get("recharge_forfait")
        and not session.get("recharge_amount")
    ):
        return redirect(
            url_for("recharge.select_amount_get")
        )

    ctx = _get_payment_context()

    if ctx["final_amount"] <= 0:
        return redirect(
            url_for("recharge.select_amount_get")
        )

    _get_or_create_payment_idempotency_key()

    # ---------------------------
    # Reloadly quote display
    # ---------------------------
    received_display = session.get("received_display")

    if not received_display:

        try:
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
                quote=quote,
            )

        except Exception:
            logger.exception(
                "Card page quote display error"
            )
            received_display = None

    # ---------------------------
    # Saved cards
    # ---------------------------
    cards = []

    user_id = session.get("user_id")

    if user_id:
        try:
            cards = CardService.get_user_cards(
                str(user_id)
            )
        except Exception as exc:
            logger.exception(
                "Load saved cards error: %s",
                exc,
            )
            cards = []

    return render_template(
        "payment/card.html",
        phone=ctx["phone"],
        amount=ctx["base_amount"],
        forfait_display=_get_forfait_display(),
        final_amount=ctx["final_amount"],
        save_card=session.get("payment_save_card", True),
        received_display=received_display,
        payment_form_nonce=_ensure_payment_form_nonce(),
        cards=cards,
    )

# ---------------------------
# Payment method
# ---------------------------
@payment_bp.get("/method")
def method_get():

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

    return render_template(
        "payment/method.html",
        phone=ctx["phone"],
        amount=amount,
        forfait_display=_get_forfait_display(),
        final_amount=ctx["final_amount"],
        selected_method=session.get("payment_selected_method", "card"),
        save_card=session.get("payment_save_card", True),
        is_forfait_minutes=False,
        received_display=received_display,
        from_wallet=from_wallet,
        payment_form_nonce=_ensure_payment_form_nonce(),
        cards=CardService.get_user_cards(session.get("user_id")),
    )

@payment_bp.post("/method")
def method_post():
    selected_method = request.form.get("selected_method", "card")
    save_card = request.form.get("save_card") == "1"

    session["payment_selected_method"] = selected_method
    session["payment_save_card"] = save_card

    if selected_method != "card":
        session["payment_toast"] = "payment.methodUnavailable"
        return redirect(url_for("payment.method_get"))

    return redirect(url_for("payment.card_get"))


# ---------------------------
# Process card payment
# ---------------------------
@payment_bp.post("/card")
def card_post():

    # ---------------------------
    # Request payload
    # ---------------------------
    data = request.get_json(
        silent=True
    ) or {}
    logger.info(
        "PAYMENT CARD POST | channel=%s | saved_card_id=%s | user_id=%s | amount=%s | nonce=%s",
        data.get("payment_channel"),
        data.get("saved_card_id"),
        session.get("user_id"),
        session.get("recharge_total_amount"),
        bool(data.get("payment_form_nonce")),
    )
    # ---------------------------
    # Method guard
    # ---------------------------
    payment_channel = _safe_str(
        data.get("payment_channel") or "card"
    )

    allowed_channels = {
        "card",
        "saved_card",
        "apple_pay",
        "google_pay",
        "wallet",
    }

    if payment_channel not in allowed_channels:
        return jsonify(
            {
                "error": "invalid_payment_channel",
            }
        ), 400

    session["payment_selected_method"] = "card"

    # ---------------------------
    # Nonce anti-bot
    # ---------------------------
    if not _validate_payment_form_nonce(data):
        logger.warning(
            "Payment nonce blocked | ip=%s",
            PaymentGuardService.client_ip(),
        )

        return jsonify(
            {
                "error": "invalid_payment_session",
            }
        ), 403

    # ---------------------------
    # Login required
    # ---------------------------
    user_id = session.get("user_id")

    if not user_id:
        return jsonify(
            {
                "error": "login_required",
            }
        ), 401

    user_id = str(user_id)

    # ---------------------------
    # Save card sync
    # ---------------------------
    if "save_card" in data:
        session["payment_save_card"] = bool(
            data.get("save_card")
        )

    # ---------------------------
    # Payment context
    # ---------------------------
    ctx = _get_payment_context()

    if ctx["final_amount"] <= 0:
        return jsonify(
            {
                "error": "invalid_amount",
            }
        ), 400

    if not ctx["recharge_amount"]:
        return jsonify(
            {
                "error": "missing_recharge_amount",
            }
        ), 400

    # ---------------------------
    # Idempotency
    # ---------------------------
    idem_key = _get_or_create_payment_idempotency_key()

    existing = IdempotencyService.get_result(
        idem_key
    )

    if existing:
        _store_payment_success_payload(
            existing
        )

        return jsonify(
            {
                "success": True,
                "already_processed": True,
            }
        ), 200

    # ---------------------------
    # Anti card testing guard
    # ---------------------------
    try:
        risk_context = PaymentGuardService.assert_allowed(
            phone=ctx["phone"],
            user_id=user_id,
            user_email=(
                session.get("user_email")
                or session.get("pending_email")
            ),
            amount=ctx["final_amount"],
        )

    except PaymentGuardError as exc:

        logger.warning(
            "Payment guard blocked | code=%s | user_id=%s | phone=%s",
            exc.code,
            user_id,
            ctx["phone"],
        )

        return jsonify(
            {
                "error": exc.code,
            }
        ), exc.status_code

    # ---------------------------
    # Metadata
    # ---------------------------
    metadata = _build_checkout_metadata(
        idem_key
    )

    idem_key = metadata.get(
        "payment_idempotency_key"
    ) or idem_key

    metadata.update(
        risk_context.get("metadata") or {}
    )

    selected_saved_card_id = _safe_str(
        data.get("saved_card_id")
    )

    # ---------------------------
    # Saved card payment
    # ---------------------------
    if selected_saved_card_id:

        selected_card = CardService.get_card(
            user_id=user_id,
            card_id=selected_saved_card_id,
        )

        if not selected_card:
            return jsonify(
                {
                    "error": "card_not_found",
                }
            ), 404

        stripe_customer_id = _safe_str(
            selected_card.get("stripe_customer_id")
        )

        stripe_payment_method_id = _safe_str(
            selected_card.get("stripe_payment_method_id")
            or selected_card.get("payment_method_id")
            or selected_card.get("stripe_card_id")
            or selected_saved_card_id
        )

        if not stripe_customer_id:
            return jsonify(
                {
                    "error": "missing_stripe_customer_id",
                }
            ), 400

        if not stripe_payment_method_id:
            return jsonify(
                {
                    "error": "missing_payment_method_id",
                }
            ), 400

        metadata["payment_channel"] = "saved_card"
        metadata["payment_method"] = "saved_card"
        metadata["saved_card_id"] = selected_saved_card_id
        metadata["saved_card_brand"] = _safe_str(
            selected_card.get("brand")
        )
        metadata["saved_card_last4"] = _safe_str(
            selected_card.get("last4")
        )
        metadata["stripe_customer_id"] = stripe_customer_id
        metadata["save_card"] = "false"

        try:
            intent = StripeService.create_saved_card_payment_intent(
                amount=ctx["final_amount"],
                currency="eur",
                payment_method_id=stripe_payment_method_id,
                metadata=metadata,
                customer_id=stripe_customer_id,
                idempotency_key=f"{idem_key}:saved:{selected_saved_card_id}",
            )

            session["last_payment_intent_id"] = _safe_get(
                intent,
                "id",
                "",
            )

            return jsonify(
                {
                    "client_secret": _safe_get(
                        intent,
                        "client_secret",
                    ),
                    "payment_intent_id": _safe_get(
                        intent,
                        "id",
                    ),
                    "status": _safe_get(
                        intent,
                        "status",
                    ),
                    "saved_card": True,
                }
            ), 200

        except ValueError as exc:

            error_code = _safe_str(
                exc
            )

            logger.warning(
                "Saved card rejected | user_id=%s | card_id=%s | error=%s",
                user_id,
                selected_saved_card_id,
                error_code,
            )

            return jsonify(
                {
                    "error": error_code,
                }
            ), 400

        except Exception as exc:

            logger.exception(
                "Saved card payment intent error: %s",
                exc,
            )

            return jsonify(
                {
                    "error": "saved_card_payment_error",
                }
            ), 400

    # ---------------------------
    # New card payment channel
    # ---------------------------
    metadata["payment_channel"] = _safe_str(
        data.get("payment_channel") or "card"
    )

    metadata["payment_method"] = "card"

    # ---------------------------
    # Save card customer
    # ---------------------------
    save_card = bool(
        session.get("payment_save_card", True)
    )

    stripe_customer_id = None

    if save_card:
        try:
            stripe_customer_id = CardService.get_or_create_stripe_customer_id(
                user_id=user_id,
                email=metadata.get("user_email"),
            )

            if stripe_customer_id:
                metadata["stripe_customer_id"] = stripe_customer_id

        except Exception:

            logger.exception(
                "Stripe customer create error"
            )

            return jsonify(
                {
                    "error": "payment_customer_error",
                }
            ), 400

    # ---------------------------
    # Create Stripe intent
    # ---------------------------
    try:
        intent = StripeService.create_payment_intent(
            amount=ctx["final_amount"],
            currency="eur",
            metadata=metadata,
            idempotency_key=idem_key,
            customer_email=metadata.get("user_email"),
            customer_id=stripe_customer_id,
            save_card=save_card,
        )

        intent_customer_id = _safe_str(
            getattr(
                intent,
                "customer",
                "",
            )
        )

        if intent_customer_id:
            metadata["stripe_customer_id"] = intent_customer_id

        session["last_payment_intent_id"] = intent.id

        return jsonify(
            {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "saved_card": False,
            }
        )

    except Exception as exc:

        logger.exception(
            "Stripe payment intent error: %s",
            exc,
        )

        return jsonify(
            {
                "error": "payment_error",
            }
        ), 400


# ---------------------------
# Stripe webhook (FINAL PRODUCTION ULTRA SAFE)
# ---------------------------
@payment_bp.post("/webhook")
def stripe_webhook_post():

    print("🔥 WEBHOOK CALLED")

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    # ---------------------------
    # Verify Stripe signature
    # ---------------------------
    try:
        event = StripeService.construct_webhook_event(
            payload,
            sig_header
        )

    except Exception as exc:

        logger.exception(
            "❌ Stripe signature error: %s",
            exc
        )

        return jsonify({"ok": False}), 400

    event_type = event.get("type")

    event_data = (
        event.get("data") or {}
    ).get("object") or {}

    metadata = dict(
        event_data.get("metadata") or {}
    )

    # ---------------------------
    # Track failed card attempts
    # ---------------------------
    if event_type in {
        "payment_intent.payment_failed",
        "payment_intent.canceled",
    }:

        try:
            PaymentGuardService.record_failed_payment(
                metadata=metadata,
            )

        except Exception:
            logger.exception(
                "Payment guard failed-event tracking error"
            )

        return jsonify(
            {
                "ok": True,
            }
        ), 200

    # ---------------------------
    # Only handle success payments
    # ---------------------------
    if event_type != "payment_intent.succeeded":
        return jsonify({"ok": True}), 200

    if _safe_str(
        event_data.get("status")
    ) != "succeeded":

        return jsonify({"ok": True}), 200

    metadata = event_data.get("metadata") or {}

    idem_key = _safe_str(
        metadata.get("payment_idempotency_key")
    )

    if not idem_key:

        return jsonify(
            {
                "ok": False,
                "error": "missing_idempotency_key",
            }
        ), 400

    # ---------------------------
    # Idempotency protection
    # ---------------------------
    existing = IdempotencyService.get_result(
        idem_key
    )

    if existing:

        return jsonify(
            {
                "ok": True,
                "deduplicated": True,
            }
        ), 200

    payment_reference = _safe_str(
        event_data.get("id")
    )
    logger.info(
        "WEBHOOK STRIPE | intent=%s | customer=%s | payment_method=%s",
        payment_reference,
        event_data.get("customer"),
        event_data.get("payment_method"),
    )
    session["last_payment_intent_id"] = (
        payment_reference
    )

    if get_existing_transaction(
        payment_reference
    ):

        logger.warning(
            "⚠️ Duplicate recharge prevented"
        )

        return jsonify(
            {
                "ok": True,
                "deduplicated": True,
            }
        ), 200

    # ---------------------------
    # Extract metadata
    # ---------------------------
    phone = _safe_str(
        metadata.get("recharge_phone")
    )

    country_iso = _safe_str(
        metadata.get("country_iso")
    ).upper()

    forfait_id_raw = _safe_str(
        metadata.get("forfait_id")
    )

    operator_id_raw = _safe_str(
        metadata.get("operator_id")
    )

    operator_name = _safe_str(
        metadata.get("operator_name")
    )

    operator_logo = _safe_str(
        metadata.get("operator_logo")
    )

    user_email = _safe_str(
        metadata.get("user_email")
    )

    user_id = _safe_str(
        metadata.get("user_id")
    )

    payment_lang = _safe_str(
        metadata.get("lang")
        or metadata.get("locale")
        or "en"
    ).lower()

    if payment_lang not in {
        "fr",
        "en",
        "ar",
        "fa",
        "ps",
        "uz",
        "tr",
        "de",
    }:
        payment_lang = "en"

    base_amount = _safe_float(
        metadata.get("base_amount"),
        0.0
    )

    charged_amount = _safe_float(
        metadata.get("charged_amount"),
        0.0
    )
    # ---------------------------
    # Payment admin details
    # ---------------------------
    payment_method_id = _safe_str(
        event_data.get("payment_method")
    )

    stripe_customer_id = _safe_str(
        event_data.get("customer")
        or metadata.get("stripe_customer_id")
    )

    payment_channel = _safe_str(
        metadata.get("payment_channel")
        or metadata.get("payment_method")
        or "card"
    )

    payment_method = _safe_str(
        metadata.get("payment_method")
        or payment_channel
        or "card"
    )

    card_brand = _safe_str(
        metadata.get("saved_card_brand")
    )

    card_last4 = _safe_str(
        metadata.get("saved_card_last4")
    )

    card_expiry = ""

    if payment_method_id and not card_last4:

        try:
            pm = StripeService.retrieve_payment_method(
                payment_method_id
            )

            card_data = getattr(
                pm,
                "card",
                None,
            )

            if card_data:
                card_brand = _safe_str(
                    getattr(card_data, "brand", "")
                )

                card_last4 = _safe_str(
                    getattr(card_data, "last4", "")
                )

                exp_month = getattr(
                    card_data,
                    "exp_month",
                    None,
                )

                exp_year = getattr(
                    card_data,
                    "exp_year",
                    None,
                )

                if exp_month and exp_year:
                    card_expiry = f"{int(exp_month):02d}/{int(exp_year)}"

        except Exception:
            logger.exception(
                "Payment method admin details error"
            )

    payment_fee = round(
        max(charged_amount - base_amount, 0),
        2,
    )

    admin_received = bool(
        charged_amount > 0
    )
    # ---------------------------
    # DEBUG IMPORTANT
    # ---------------------------
    logger.info(
        "WEBHOOK DEBUG | operator_id_raw=%s | forfait_id=%s",
        operator_id_raw,
        forfait_id_raw,
    )

    # ---------------------------
    # Validation sécurité
    # ---------------------------
    if not phone or base_amount <= 0:

        IdempotencyService.store_result(
            idem_key,
            {
                "status": "FAILED",
                "reason": "invalid_metadata",
            },
        )

        return jsonify({"ok": True}), 200

    stripe_amount = (
        _safe_float(
            event_data.get("amount_received"),
            0.0
        ) / 100.0
    )

    stripe_currency = _safe_str(
        event_data.get("currency")
    ).lower()

    if stripe_currency != "eur":

        IdempotencyService.store_result(
            idem_key,
            {
                "status": "FAILED",
                "reason": "invalid_currency",
            },
        )

        return jsonify({"ok": True}), 200

    if abs(
        stripe_amount - charged_amount
    ) > 0.01:

        IdempotencyService.store_result(
            idem_key,
            {
                "status": "FAILED",
                "reason": "amount_mismatch",
            },
        )

        return jsonify({"ok": True}), 200

    # ---------------------------
    # 🔒 FORFAIT / DATA LOGIC
    # ---------------------------
    plan_id = None

    if forfait_id_raw:

        try:
            plan_id = str(forfait_id_raw).strip()

        except Exception:

            plans = session.get(
                "recharge_data_plans"
            ) or []

            matched_plan = next(
                (
                    p for p in plans
                    if str(
                        p.get("name")
                    ) == str(forfait_id_raw)
                ),
                None
            )

            if matched_plan:
                plan_id = matched_plan.get("id")

    amount_value = round(
        base_amount,
        2
    )

    # ---------------------------
    # FIX CRITIQUE OPERATOR ID
    # ---------------------------
    try:
        operator_id = int(operator_id_raw)

    except Exception:
        operator_id = None

    # ---------------------------
    # sécurité DATA
    # ---------------------------
    if forfait_id_raw and not operator_id:

        logger.error(
            "❌ Missing operator_id for DATA recharge"
        )

        IdempotencyService.store_result(
            idem_key,
            {
                "status": "FAILED",
                "reason": "missing_operator_id",
            },
        )

        return jsonify({"ok": True}), 200

    # ---------------------------
    # PROCESS RECHARGE
    # ---------------------------
    try:

        result = process_recharge(
            payment_reference=payment_reference,
            phone=phone,
            country_iso=country_iso,
            amount=amount_value,
            plan_id=plan_id,
            operator_id=operator_id,
            user_id=user_id or session.get("user_id"),
            metadata={
                "flow": "stripe_webhook",
                "payment_intent_id": payment_reference,
                "payment_idempotency_key": idem_key,

                "stripe_id": payment_reference,
                "stripe_customer_id": stripe_customer_id,
                "payment_method_id": payment_method_id,
                "payment_method": payment_method,
                "payment_channel": payment_channel,

                "base_amount": f"{base_amount:.2f}",
                "charged_amount": f"{charged_amount:.2f}",
                "fee": f"{payment_fee:.2f}",
                "tax": f"{payment_fee:.2f}",
                "total": f"{charged_amount:.2f}",

                "card_brand": card_brand,
                "card_last4": card_last4,
                "card_expiry": card_expiry,

                "admin_received": str(admin_received).lower(),
            },
        )

        payload_obj = _build_success_payload(
            base_amount=base_amount,
            charged_amount=charged_amount,
            transaction_id=result.transaction_id,
            transaction_reference=result.custom_identifier,
            order_reference=(
                metadata.get("order_reference")
                or metadata.get("order_number")
            ),
        )
        payload_obj["lang"] = payment_lang
        payload_obj["locale"] = payment_lang
        # ---------------------------
        # Admin payment details
        # ---------------------------
        payload_obj.update({
            "stripe_id": payment_reference,
            "payment_intent_id": payment_reference,
            "stripe_customer_id": stripe_customer_id,
            "payment_method_id": payment_method_id,
            "payment_method": payment_method,
            "payment_channel": payment_channel,

            "fee": payment_fee,
            "tax": payment_fee,
            "total": round(charged_amount, 2),

            "card_brand": card_brand,
            "card_last4": card_last4,
            "card_expiry": card_expiry,

            "admin_received": admin_received,
        })
        # ---------------------------
        # Gestion erreurs recharge
        # ---------------------------
        if result.status in {"FAILED", "REFUNDED"}:

         payload_obj["status"] = "FAILED"
         payload_obj["reason"] = "recharge_failed"

        else:

         payload_obj["status"] = "SUCCESS"



        # ---------------------------
        # Save result
        # ---------------------------
        IdempotencyService.store_result(idem_key, payload_obj)
        _store_payment_success_payload(payload_obj)

        # ---------------------------
        # Save card
        # ---------------------------
        try:
            save_card = (
                _safe_str(metadata.get("save_card")).lower()
                == "true"
            )

            payment_method_id = _safe_str(
                event_data.get("payment_method")
            )

            stripe_customer_id = _safe_str(
                event_data.get("customer")
                or metadata.get("stripe_customer_id")
            )

            logger.info(
                "SAVE CARD CHECK | user_id=%s | save_card=%s | payment_method=%s | customer=%s",
                user_id,
                save_card,
                payment_method_id,
                stripe_customer_id,
            )

            if save_card and user_id and payment_method_id:

                pm = StripeService.retrieve_payment_method(
                    payment_method_id
                )

                card_data = getattr(
                    pm,
                    "card",
                    None,
                )

                if card_data:
                    CardService.save_card(
                        user_id=str(user_id),
                        payment_method=pm,
                        stripe_customer_id=stripe_customer_id,
                    )

                    logger.info(
                        "CARD SAVED | user_id=%s | payment_method=%s | customer=%s",
                        user_id,
                        payment_method_id,
                        stripe_customer_id,
                    )

        except Exception as e:
            logger.exception(
                "CARD SAVE ERROR: %s",
                e,
            )

        # ---------------------------
        # Email
        # ---------------------------
        if user_email and result.status == "SUCCESS":
            try:
                EmailService.send_payment_success(
                    email=user_email,
                    payload=payload_obj,
                    lang=payment_lang,
                    phone=phone,
                    country_name=country_iso,
                    operator_name=operator_name,
                    operator_logo=operator_logo,
                )
            except Exception:
                logger.exception("Email error")

    except TransactionServiceError as e:
        logger.exception("Recharge error: %s", e)

        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "recharge_error"},
        )

        return jsonify({"ok": True}), 200

    except Exception as e:
        logger.exception("Webhook unexpected error: %s", e)

        IdempotencyService.store_result(
            idem_key,
            {"status": "FAILED", "reason": "unexpected_error"},
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
# Payment success page (FINAL PRODUCTION STABLE)
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
    # 🔒 PROTECTION
    # ---------------------------
    if not payment_intent_id:

        ctx = _get_payment_context()

        return render_template(
            "payment/success.html",
            status="processing",
            amount=ctx.get("recharge_amount", 0),
            date_iso=datetime.now(timezone.utc).isoformat(),
            order_number="...",
            reference="...",
            forfait_display=forfait_display,
            received_display=received_display,
            phone=session.get("recharge_phone"),
        )

    # ---------------------------
    # 🔥 AFFICHAGE IMMÉDIAT
    # ---------------------------
    if not payload:

        formatted_ref = _safe_str(
            session.get("payment_order_reference")
        )

        if not formatted_ref and payment_intent_id:

            try:
                intent = StripeService.retrieve_payment(
                    payment_intent_id
                )

                intent_metadata = dict(
                    getattr(intent, "metadata", {}) or {}
                )

                formatted_ref = _safe_str(
                    intent_metadata.get("order_reference")
                    or intent_metadata.get("order_number")
                )

            except Exception:
                logger.exception(
                    "Payment success order reference metadata error"
                )

        if not formatted_ref:
            formatted_ref = _get_or_create_order_reference()

        payload = {
            "status": "PROCESSING",

            "amount": _safe_float(
                session.get("recharge_amount")
            ),

            "date_iso": datetime.now(
                timezone.utc
            ).isoformat(),

            "order_number": formatted_ref,
            "reference": formatted_ref,

            "transaction_reference": payment_intent_id,
            "reloadly_reference": payment_intent_id,

            "transaction_id": None,
        }

        session["payment_success_payload"] = payload

        return render_template(
            "payment/success.html",
            status="processing",
            amount=payload.get("amount", 0),
            date_iso=payload.get("date_iso"),
            order_number=payload.get("order_number", "..."),
            reference=payload.get("reference", "..."),
            forfait_display=forfait_display,
            received_display=received_display,
            phone=session.get("recharge_phone"),
        )

    # ---------------------------
    # 🔄 SYNC STATUS (Reloadly)
    # ---------------------------
    try:

        transaction_id = payload.get("transaction_id")
        reference = payload.get("transaction_reference")

        if transaction_id or reference:

            tx = refresh_transaction_status(
                reference=reference,
                transaction_id=transaction_id,
            )

            payload["transaction_id"] = tx.transaction_id

            payload["transaction_reference"] = (
                tx.custom_identifier
                or reference
            )

            payload["reloadly_reference"] = (
                tx.custom_identifier
                or payload.get("reloadly_reference")
            )

            session["payment_success_payload"] = payload

            # ---------------------------
            # PROCESSING
            # ---------------------------
            if tx.status == "PROCESSING":

                return render_template(
                    "payment/success.html",
                    status="processing",
                    amount=payload.get("amount", 0),
                    date_iso=payload.get("date_iso"),
                    order_number=payload.get("order_number", "..."),
                    reference=payload.get("reference", "..."),
                    forfait_display=forfait_display,
                    received_display=received_display,
                    phone=session.get("recharge_phone"),
                )

            # ---------------------------
            # FAILED
            # ---------------------------
            if tx.status in {
                "FAILED",
                "REFUNDED",
            }:

                return render_template(
                    "payment/success.html",
                    status="failed",
                    amount=payload.get("amount", 0),
                    date_iso=payload.get("date_iso"),
                    order_number=payload.get("order_number", "..."),
                    reference=payload.get("reference", "..."),
                    forfait_display=forfait_display,
                    received_display=received_display,
                    phone=session.get("recharge_phone"),
                )

    # ---------------------------
    # Reloadly transaction
    # not ready yet
    # ---------------------------
    except InvalidTransactionInputError:

        return render_template(
            "payment/success.html",
            status="processing",
            amount=payload.get("amount", 0),
            date_iso=payload.get("date_iso"),
            order_number=payload.get("order_number", "..."),
            reference=payload.get("reference", "..."),
            forfait_display=forfait_display,
            received_display=received_display,
            phone=session.get("recharge_phone"),
        )

    # ---------------------------
    # Unexpected error
    # ---------------------------
    except Exception as e:

        logger.exception(
            "⚠️ STATUS REFRESH ERROR: %s",
            e
        )

        return render_template(
            "payment/success.html",
            status="processing",
            amount=payload.get("amount", 0),
            date_iso=payload.get("date_iso"),
            order_number=payload.get("order_number", "..."),
            reference=payload.get("reference", "..."),
            forfait_display=forfait_display,
            received_display=received_display,
            phone=session.get("recharge_phone"),
        )

    # ---------------------------
    # ✅ SUCCESS FINAL
    # ---------------------------
    return render_template(
        "payment/success.html",
        status="success",
        amount=payload.get("amount", 0),
        date_iso=payload.get("date_iso"),
        order_number=payload.get("order_number", "..."),
        reference=payload.get("reference", "..."),
        forfait_display=forfait_display,
        received_display=received_display,
        phone=session.get("recharge_phone"),
    )
# ---------------------------
# Set default card
# ---------------------------
@payment_bp.post("/cards/<card_id>/default")
def set_default_card_post(card_id):

    user_id = session.get("user_id")

    if not user_id:
        return redirect(
            url_for("auth.login_get")
        )

    CardService.set_default_card(
        user_id=str(user_id),
        card_id=card_id,
    )

    return redirect(
        url_for("account.card_storage_get")
    )


# ---------------------------
# Delete card
# ---------------------------
@payment_bp.post("/cards/<card_id>/delete")
def delete_card_post(card_id):

    user_id = session.get("user_id")

    if not user_id:
        return redirect(
            url_for("auth.login_get")
        )

    CardService.delete_card(
        card_id=card_id,
        user_id=str(user_id),
    )

    return redirect(
        url_for("account.card_storage_get")
    )
# ---------------------------
# payment_bp.post
# ---------------------------
@payment_bp.post("/success/finish")
def success_finish_post():
    session.pop("payment_success_payload", None)
    session.pop("payment_idempotency_key", None)
    session.pop("payment_form_nonce", None)
    session.pop("payment_toast", None)
    session.pop("payment_selected_method", None)
    session.pop("payment_save_card", None)
    session.pop("last_payment_intent_id", None)
    session.pop("payment_order_reference", None)
    session.pop("last_order_reference", None)

    session.pop("recharge_phone", None)
    session.pop("recharge_amount", None)
    session.pop("recharge_total_amount", None)
    session.pop("recharge_forfait", None)
    session.pop("recharge_operator", None)
    session.pop("country_iso", None)

    return redirect(url_for("recharge.enter_number_get"))