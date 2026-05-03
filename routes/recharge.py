# ---------------------------
# Feature: Recharge Routes
# ---------------------------

from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from services.payment.currency_service import CurrencyService
from services.payment.fees_service import FeesService
from services.recharge.recharge_service import (
    detect_country_iso_from_phone,
    is_phone_length_valid,
    normalize_phone_e164_light,
)
from services.reloadly.airtime_service import get_topup_status
from services.reloadly.data_service import (
    get_reloadly_plans,
    get_reloadly_quote,
)
from services.reloadly.operators_service import (
    get_reloadly_operator_amounts,
    get_reloadly_operators_by_country,
    lookup_phone_number,
)
from services.reloadly.transaction_service import (
    TransactionServiceError,
    build_transaction_reference,
    process_recharge,
    refresh_transaction_status,
)

logger = logging.getLogger(__name__)

recharge_bp = Blueprint("recharge", __name__, url_prefix="/recharge")

# Compat ancien code
get_reloadly_operator_auto_detect = lookup_phone_number


# ---------------------------
# Helpers
# ---------------------------

def get_city_for_country(iso):
    file_path = Path("static/data/country_cities.json")

    if not file_path.exists():
        return "default"

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return "default"

    return data.get((iso or "").upper(), "default")


def _session_operator():
    operator = session.get("recharge_operator") or {}
    return operator if isinstance(operator, dict) else {}


def _get_payment_reference() -> str:
    """
    Source UNIQUE de référence paiement (ANTI DOUBLE RECHARGE)
    """

    candidates = [
        session.get("stripe_payment_intent_id"),
        session.get("payment_intent_id"),
        session.get("checkout_session_id"),
        session.get("order_id"),
        session.get("recharge_payment_reference"),
    ]

    for value in candidates:
        if value:
            return str(value)

    # ---------------------------
    # 🔒 FALLBACK SAFE (UUID)
    # ---------------------------
    import uuid

    fallback = f"fallback:{uuid.uuid4()}"
    session["recharge_payment_reference"] = fallback  # 🔥 IMPORTANT

    return fallback
# ---------------------------
# Clear forfait
# ---------------------------
@recharge_bp.post("/clear-forfait")
def clear_forfait():
    session.pop("recharge_forfait", None)
    return jsonify({"ok": True})


    # ---------------------------
    # 🔒 select-forfait
    # ---------------------------
@recharge_bp.get("/select-forfait")
def select_forfait_get():

    phone = session.get("recharge_phone")

    if not phone:
        return redirect(url_for("recharge.enter_number_get"))

    country_iso = detect_country_iso_from_phone(phone)

    operator = _session_operator()

    # ---------------------------
    # si operator sans data → trouver version DATA du même opérateur
    # ---------------------------
    if operator and not operator.get("supports_data"):

        operators = get_reloadly_operators_by_country(country_iso)

        base_name = (operator.get("name") or "").lower()

        data_match = next(
            (
                op for op in operators
                if op.get("supports_data")
                and base_name.split("data")[0].strip()
                in (op.get("name") or "").lower()
            ),
            None
        )

        if data_match:
            operator = data_match
            session["recharge_operator"] = operator

    # ---------------------------
    # aucun operator → fallback auto detect
    # ---------------------------
    if not operator:

        operators = get_reloadly_operators_by_country(country_iso)

        operators = [
            op for op in operators
            if op.get("supports_data")
        ]

        if operators:
            operator = operators[0]
            session["recharge_operator"] = operator

    logger.info("📡 OPERATOR FINAL: %s", operator)

    # ---------------------------
    # Get plans
    # ---------------------------
    plans = []

    operator_id = (
        (operator or {}).get("id")
        or ((operator or {}).get("raw") or {}).get("operatorId")
    )

    if operator_id:
        plans = get_reloadly_plans(operator)

        print("FORFAITS FINAL:", plans)

    # ---------------------------
    # fallback UX
    # ---------------------------
    if not plans:
        return render_template(
            "recharge/select_forfait.html",
            plans=[],
            operator=operator,
            phone=phone,
            no_plans=True
        )

    return render_template(
        "recharge/select_forfait.html",
        plans=plans,
        operator=operator,
        phone=phone,
        no_plans=False
    )

# ---------------------------
# Select Forfait (POST)
# ---------------------------

@recharge_bp.post("/select-forfait")
def select_forfait_post():
    session.pop("received_display", None)
    data = request.get_json(silent=True) or {}

    gb = data.get("gb")
    price = data.get("price")
    plan_id = data.get("id")

    if not gb or not price or not plan_id:
        return jsonify({"ok": False}), 400

    # ---------------------------
    # Save forfait
    # ---------------------------
    session["recharge_forfait"] = {
        "id": int(plan_id),
        "gb": gb,
        "price": price,
    }

    # ---------------------------
    # 🔒 LOCK operator (IMPORTANT)
    # ---------------------------
    operator = session.get("recharge_operator")

    if operator:
        session["recharge_operator"] = operator

    return jsonify({"ok": True})

# ---------------------------
# API: get forfaits live (OPTIMIZED)
# ---------------------------
@recharge_bp.post("/api/forfaits")
def api_forfaits():

    operator = session.get("recharge_operator")
    country_iso = session.get("country_iso")

    if not operator:
        return jsonify({"error": "no_operator"}), 400

    # ---------------------------
    # 🔒 CACHE (ULTRA IMPORTANT)
    # ---------------------------
    cached_plans = session.get("recharge_data_plans")

    if cached_plans:
        return jsonify({"plans": cached_plans})

    # ---------------------------
    # 🔥 FIX CRITIQUE : FORCER OPERATOR DATA
    # ---------------------------
    if not operator.get("supports_data"):

        operators = get_reloadly_operators_by_country(country_iso)

        base_name = (operator.get("name") or "").lower()

        data_operator = next(
            (
                op for op in operators
                if op.get("supports_data")
                and base_name.split("(")[0].strip()
                in (op.get("name") or "").lower()
            ),
            None
        )

        if data_operator:
            operator = data_operator
            session["recharge_operator"] = operator  # 🔒 IMPORTANT

    # ---------------------------
    # Get plans (LIVE - 1 seule fois)
    # ---------------------------
    plans = get_reloadly_plans(operator)

    session["recharge_data_plans"] = plans

    return jsonify({"plans": plans})

# ---------------------------
# API Phone Lookup
# ---------------------------

@recharge_bp.route("/api/lookup-number", methods=["POST"])
def lookup_number():
    data = request.get_json(silent=True) or {}

    phone = normalize_phone_e164_light(data.get("phone"))
    country = (data.get("country") or "").strip().upper()

    if not phone or not is_phone_length_valid(phone) or not country:
        return jsonify({"valid": False}), 400

    result = lookup_phone_number(phone, country)

    if not result:
        return jsonify({"valid": False})

    # ---------------------------
    # 🔥 STORE FULL OPERATOR (FIX CRITIQUE)
    # ---------------------------
    session["recharge_operator"] = result

    # ---------------------------
    # ensure normalized keys (SAFE)
    # ---------------------------
    session["recharge_operator"].update({
        "id": (
            result.get("id")
            or result.get("operatorId")
            or result.get("operator_id")
            or (result.get("raw") or {}).get("operatorId")
            or (result.get("raw") or {}).get("id")
        ),
        "name": result.get("name"),
        "logo_url": result.get("logo_url"),
        "country_iso": (
            result.get("country_iso")
            or result.get("countryCode")
            or result.get("country_code")
            or country
        ),
      "supports_data": bool(
      result.get("data")
      or result.get("bundle")
      or result.get("comboProduct")

        ),
        "raw": result.get("raw") or result,
    })

    return jsonify(
        {
            "valid": True,
            "operatorId": session["recharge_operator"].get("id"),
            "operatorName": session["recharge_operator"].get("name"),
            "logoUrl": session["recharge_operator"].get("logo_url"),
            "countryCode": session["recharge_operator"].get("country_iso"),
        }
    )

# ---------------------------
# Enter number (GET)
# ---------------------------

@recharge_bp.get("/enter-number")
def enter_number_get():
    print("SESSION ENTER NUMBER:", dict(session))

    # ---------------------------
    # RESET FLOW (IMPORTANT)
    # ---------------------------
    session.pop("recharge_forfait", None)
    session.pop("recharge_operator", None)
    session.pop("recharge_amount", None)
    session.pop("recharge_total_amount", None)

    initial_phone = session.get("recharge_phone", "+93")
    country_iso = detect_country_iso_from_phone(initial_phone) or "AF"
    city = get_city_for_country(country_iso)

    return render_template(
    "recharge/enter_number.html",
    initial_phone=initial_phone,
    country_iso=country_iso,
    city=city,
    canonical_url="https://yeslek.com/recharge/enter-number",

    # ---------------------------
    # SEO
    # ---------------------------
    seo_title="Recharge mobile internationale | Yeslek",
    seo_description="Envoyez du crédit mobile instantanément dans plus de 150 pays avec Yeslek. Recharge rapide et sécurisée."
)


# ---------------------------
# Enter number (POST)
# ---------------------------

@recharge_bp.post("/enter-number")
def enter_number_post():
    raw = request.form.get("phone", "")
    phone = normalize_phone_e164_light(raw)

    country_iso = (
        request.form.get("country_iso")
        or detect_country_iso_from_phone(phone)
        or "AF"
    )

    if not phone or not is_phone_length_valid(phone):
        city = get_city_for_country(country_iso)

        return render_template(
            "recharge/enter_number.html",
            initial_phone=phone or "+93",
            country_iso=country_iso,
            city=city,
            phone_error=True,
        ), 400

    session["recharge_phone"] = phone
    session["country_iso"] = country_iso.upper()

    # ---------------------------
    # 🔥 FIX: PRELOAD OPERATOR + DATA + AMOUNTS
    # ---------------------------
    try:
        operator = lookup_phone_number(phone, country_iso)

        if operator:
            session["recharge_operator"] = operator

            # 👉 DATA plans (forfaits)
            if operator.get("supports_data"):
                try:
                    plans = get_reloadly_plans(operator)
                except Exception:
                    plans = []
            else:
                plans = []

            session["recharge_data_plans"] = plans

            # 👉 Amounts
            try:
                amounts = get_reloadly_operator_amounts(operator.get("id"))
            except Exception:
                amounts = {}

            session["recharge_amounts"] = amounts

    except Exception:
        session["recharge_data_plans"] = []
        session["recharge_amounts"] = {}

    return redirect(url_for("recharge.select_amount_get"))


# ---------------------------
# Select Operator (GET)
# ---------------------------

@recharge_bp.get("/select-operator")
def select_operator_get():
    phone = session.get("recharge_phone")

    if not phone:
        return redirect(url_for("recharge.enter_number_get"))

    country_iso = detect_country_iso_from_phone(phone) or "FR"
    operators = get_reloadly_operators_by_country(country_iso)

    return render_template(
        "recharge/select_operator.html",
        operators=operators,
        phone=phone,
    )


# ---------------------------
# Select Operator (POST)
# ---------------------------

@recharge_bp.route("/select-operator", methods=["POST"])
def select_operator_post():
    operator_id = request.form.get("operator_id")
    country_iso = request.form.get("country_iso") or session.get("country_iso")

    if not operator_id:
        return redirect(url_for("recharge.select_operator_get"))

    # ---------------------------
    # 🔥 GET FULL OPERATOR FROM RELOADLY
    # ---------------------------
    operators = get_reloadly_operators_by_country(country_iso)

    full_operator = next(
        (op for op in operators if str(op.get("id")) == str(operator_id)),
        None
    )

    if not full_operator:
        return redirect(url_for("recharge.select_operator_get"))

    # ---------------------------
    # STORE FULL OPERATOR
    # ---------------------------
    session["recharge_operator"] = full_operator

    if full_operator.get("supports_data"):
        return redirect(url_for("recharge.select_forfait_get"))

    return redirect(url_for("recharge.select_amount_get"))


# ---------------------------
# Feature: Select amount (GET)
# ---------------------------
@recharge_bp.get("/select-amount")
def select_amount_get():

    # AUTO CLEAR SAFE
    if request.args.get("reset") == "1":
        session.pop("recharge_forfait", None)

    session.pop("received_display", None)
    phone = session.get("recharge_phone")

    if not phone:
        return redirect(url_for("recharge.enter_number_get"))

    country_iso = detect_country_iso_from_phone(phone) or "FR"
    operator = _session_operator()

    # ---------------------------
    # Operator detection
    # ---------------------------
    if not operator:
        operator = get_reloadly_operator_auto_detect(phone, country_iso) or {}

    # 🔒 LOCK operator (IMPORTANT)
    if operator:
        session["recharge_operator"] = operator

    operator_id = operator.get("id")

    # ---------------------------
    # Amounts
    # ---------------------------
    operator_amounts = {
        "fixedAmounts": [],
        "minAmount": 2,
        "maxAmount": 50,
    }

    if operator_id:
        operator_amounts = get_reloadly_operator_amounts(operator_id) or operator_amounts

    # ---------------------------
    # Currency & Fees
    # ---------------------------
    currency = CurrencyService.currency_from_phone(phone)
    tax_rate = FeesService.get_tax_rate(currency)

    operator["currency_code"] = currency

    destination_currency = (
        operator.get("destinationCurrencyCode")
        or (operator.get("raw") or {}).get("destinationCurrencyCode")
    )

    try:
        amount = float(session.get("recharge_amount", 5.00))
    except Exception:
        amount = 5.00

    breakdown = FeesService.breakdown(amount, currency)

    # ---------------------------
    # Quote
    # ---------------------------
    quote = None

    if operator_id:
        quote = get_reloadly_quote(
            operator_id=operator_id,
            amount=amount,
            phone=phone,
            country_iso=country_iso,
        )

    # ---------------------------
    # Received
    # ---------------------------
    received_display = CurrencyService.received_display_value(
        phone=phone,
        amount=amount,
        selected_forfait=session.get("recharge_forfait"),
        quote=quote,
    )
    session["received_display"] = received_display
    
    # ---------------------------
    # Template
    # ---------------------------
    return render_template(
        "recharge/select_amount.html",
        phone=phone,
        country_iso=country_iso,
        operator=operator,
        amounts=operator_amounts,
        tax_rate=breakdown["tax_rate"],
        amount=breakdown["amount"],
        tax=breakdown["tax"],
        total=breakdown["total"],
        currency_code=currency,
        received_display=received_display,
        destination_currency=destination_currency,
    )


# ---------------------------
# Select amount (POST) FINAL SAFE
# ---------------------------

@recharge_bp.post("/select-amount")
def select_amount_post():

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # ---------------------------
    # 🔒 LOGIN CHECK
    # ---------------------------
    if not session.get("user_id"):

        if is_ajax:
            return jsonify({
                "ok": False,
                "redirect": url_for("auth.login", next=url_for("payment.method_get"))
            }), 401

        return redirect(url_for("auth.login", next=request.path))

    # ---------------------------
    # PHONE CHECK
    # ---------------------------
    phone = session.get("recharge_phone")

    if not phone:
        if is_ajax:
            return jsonify({"ok": False}), 400
        return redirect(url_for("recharge.enter_number_get"))

    amount = request.form.get("amount")

    # ---------------------------
    # 🔥 SUPPORT FORFAIT
    # ---------------------------
    forfait = session.get("recharge_forfait")

    try:
        amount = float(amount)
    except Exception:
        if isinstance(forfait, dict) and forfait.get("price"):
            try:
                amount = float(forfait.get("price"))
            except Exception:
                if is_ajax:
                    return jsonify({"ok": False}), 400
                return redirect(url_for("recharge.select_amount_get"))
        else:
            if is_ajax:
                return jsonify({"ok": False}), 400
            return redirect(url_for("recharge.select_amount_get"))

    # ---------------------------
    # VALIDATION
    # ---------------------------
    MIN_AMOUNT = 2.0
    MAX_AMOUNT = 40.0

    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        if is_ajax:
            return jsonify({"ok": False}), 400
        return redirect(url_for("recharge.select_amount_get"))

    amount = max(MIN_AMOUNT, min(MAX_AMOUNT, amount))

    # ---------------------------
    # Currency & breakdown
    # ---------------------------
    currency = CurrencyService.currency_from_phone(phone)
    breakdown = FeesService.breakdown(amount, currency)

    # ---------------------------
    # RECEIVED DISPLAY
    # ---------------------------
    try:
        from services.reloadly.data_service import get_reloadly_quote

        operator = session.get("recharge_operator") or {}
        operator_id = operator.get("id")
        country_iso = session.get("country_iso")

        quote = None

        if operator_id:
            quote = get_reloadly_quote(
                operator_id=operator_id,
                amount=amount,
                phone=phone,
                country_iso=country_iso,
            )

        received_display = CurrencyService.received_display_value(
            phone=phone,
            amount=amount,
            selected_forfait=forfait,
            quote=quote,
        )

        session["received_display"] = received_display

    except Exception:
        session["received_display"] = None

    # ---------------------------
    # SESSION
    # ---------------------------
    session["recharge_amount"] = float(amount)
    session["recharge_total_amount"] = float(breakdown["total"])

    # ---------------------------
    # RESET STRIPE IDEMPOTENCY
    # ---------------------------
    session.pop("payment_idempotency_key", None)
    session.pop("last_payment_amount", None)
    session.pop("payment_hash", None)

    session.modified = True

    # ---------------------------
    # ✅ AJAX RESPONSE (CRITICAL)
    # ---------------------------
    if is_ajax:
        return jsonify({
            "ok": True,
            "amount": amount
        })

    # ---------------------------
    # NORMAL FLOW
    # ---------------------------
    return redirect(url_for("payment.method_get"))

# ---------------------------
# Execute Topup (DISABLED)
# ---------------------------

@recharge_bp.post("/execute")
def execute_recharge():
    """
    ⚠️ Désactivé volontairement
    Toute recharge doit passer UNIQUEMENT par Stripe webhook
    pour éviter les doubles transactions.
    """
    return jsonify({
        "ok": False,
        "error": "disabled"
    }), 403


# ---------------------------
# Status
# ---------------------------

@recharge_bp.get("/status")
def recharge_status():
    tx = session.get("last_transaction_id")
    reference = session.get("last_transaction_reference")

    if not tx and not reference:
        return jsonify({"ok": False, "message": "No transaction found"}), 404

    try:
        result = refresh_transaction_status(
            reference=reference or build_transaction_reference(
                payment_reference=_get_payment_reference(),
                phone=session.get("recharge_phone"),
                amount=session.get("recharge_amount"),
                plan_id=(session.get("recharge_forfait") or {}).get("id"),
                operator_id=(_session_operator() or {}).get("id"),
                country_iso=session.get("country_iso"),
            ),
            transaction_id=tx,
        )

        session["last_transaction_id"] = result.transaction_id

        return jsonify({
            "ok": True,
            "status": result.status,
            "transaction_id": result.transaction_id,
            "reference": result.custom_identifier,
        })

    except Exception as exc:
        logger.exception("Recharge status error: %s", exc)
        return jsonify({"ok": False, "message": "Status unavailable"}), 500


# ---------------------------
# AJAX Quote (FINAL PRODUCTION)
# ---------------------------

@recharge_bp.post("/api/quote")
def api_quote():
    phone = session.get("recharge_phone")
    operator = _session_operator()
    country_iso = session.get("country_iso") or "FR"

    if not phone or not operator:
        return jsonify({"ok": False}), 401

    data = request.get_json(silent=True) or {}
    amount = data.get("amount")

    try:
        amount = float(amount)
    except Exception:
        return jsonify({"ok": False}), 400

    # ---------------------------
    # Feature: Amount validation (SECURE)
    # ---------------------------

    MIN_AMOUNT = 2.0
    MAX_AMOUNT = 40.0

    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        return jsonify({
            "ok": False,
            "error": "invalid_amount",
            "min": MIN_AMOUNT,
            "max": MAX_AMOUNT
        }), 400

    # clamp sécurité
    amount = max(MIN_AMOUNT, min(MAX_AMOUNT, amount))

    operator_id = operator.get("id")

    # ---------------------------
    # Quote
    # ---------------------------

    quote = None

    if operator_id:
        quote = get_reloadly_quote(
            operator_id=operator_id,
            amount=amount,
            phone=phone,
            country_iso=country_iso,
        )

    # log propre (prod)
    logger.info("Reloadly quote: %s", quote)

    # ---------------------------
    # Currency
    # ---------------------------

    currency = None

    if quote:
        currency = (
            quote.get("destinationCurrencyCode")
            or quote.get("currencyCode")
        )

    if not currency:
        currency = operator.get("destinationCurrencyCode") or "EUR"

    # ---------------------------
    # Received
    # ---------------------------

    received = None

    if quote and quote.get("destinationAmount"):
        received = f"{quote['destinationAmount']:.2f} {currency}"

    if not received:
        received = "—"

    # ---------------------------
    # Response
    # ---------------------------

    return jsonify({
        "ok": True,
        "received": received,
        "destinationCurrency": currency,
        "min": MIN_AMOUNT,
        "max": MAX_AMOUNT
    })

# ---------------------------
# API Fees (FORFAIT + AMOUNT UI)
# ---------------------------

@recharge_bp.post("/api/fees")
def api_fees():

    phone = session.get("recharge_phone")

    if not phone:
        return jsonify({"ok": False}), 400

    data = request.get_json(silent=True) or {}
    amount = data.get("amount")

    try:
        amount = float(amount)
    except Exception:
        return jsonify({"ok": False}), 400

    # ---------------------------
    # VALIDATION (same as select_amount)
    # ---------------------------
    MIN_AMOUNT = 2.0
    MAX_AMOUNT = 40.0

    if amount < MIN_AMOUNT or amount > MAX_AMOUNT:
        return jsonify({
            "ok": False,
            "min": MIN_AMOUNT,
            "max": MAX_AMOUNT
        }), 400

    amount = max(MIN_AMOUNT, min(MAX_AMOUNT, amount))

    # ---------------------------
    # FEES SERVICE (SOURCE UNIQUE)
    # ---------------------------
    currency = CurrencyService.currency_from_phone(phone)
    breakdown = FeesService.breakdown(amount, currency)

    return jsonify({
        "ok": True,
        "amount": breakdown["amount"],
        "tax": breakdown["tax"],
        "total": breakdown["total"],
        "currency": currency
    })