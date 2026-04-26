# ---------------------------
# Feature: Reloadly Operators Service (FINAL SAFE)
# ---------------------------

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from config import RELOADLY_BASE_URL
from services.reloadly.auth_service import clear_reloadly_token, get_reloadly_token, _safe_request

logger = logging.getLogger(__name__)

RELOADLY_V1_URL = f"{RELOADLY_BASE_URL}/v1"


# ---------------------------
# Helpers
# ---------------------------

def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")


def _normalize_country_iso(country_iso: str | None) -> str:
    return str(country_iso or "").strip().upper()


def _extract_local_number(phone: str) -> str:
    normalized = _normalize_phone(phone)
    return normalized[1:] if normalized.startswith("+") else normalized


def _build_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/com.reloadly.topups-v1+json",
    }


def _first_logo_url(logo_urls: Any) -> Optional[str]:
    if not logo_urls:
        return None

    first = logo_urls[0]

    if isinstance(first, dict):
        return first.get("url")

    if isinstance(first, str):
        return first

    return None


def _extract_reloadly_error(response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text or "Reloadly error"

    return data.get("message") or data.get("errorCode") or response.text or "Reloadly error"


def _request_with_token_retry(url: str):
    token = get_reloadly_token()
    headers = _build_headers(token)
    response = _safe_request("GET", url, headers=headers, timeout=15)

    if response.status_code == 401:
        clear_reloadly_token()
        token = get_reloadly_token(force_refresh=True)
        headers = _build_headers(token)
        response = _safe_request("GET", url, headers=headers, timeout=15)

    return response


# ---------------------------
# 🔥 FIX CRITIQUE
# ---------------------------
def _map_operator(data: Dict[str, Any]) -> Dict[str, Any]:
    country = data.get("country") or {}

    # 🔥 FIX ROBUSTE DATA DETECTION
    supports_data = (
        data.get("data") is True
        or data.get("supportsData") is True
        or data.get("bundle") is True  # fallback important
    )

    return {
        "id": data.get("operatorId") or data.get("id"),
        "name": data.get("name"),
        "logo_url": _first_logo_url(data.get("logoUrls")),

        "country_name": country.get("name"),
        "country_iso": country.get("isoName"),

        # 🔥 FIX IMPORTANT
        "supports_data": bool(supports_data),

        "supports_bundles": bool(data.get("bundle") or data.get("supportsBundles")),
        "supports_pin": bool(data.get("pin")),
        "supports_local_amounts": bool(data.get("supportsLocalAmounts")),

        "denomination_type": data.get("denominationType"),

        "destination_currency_code": data.get("destinationCurrencyCode"),
        "sender_currency_code": data.get("senderCurrencyCode"),

        "min_amount": data.get("minAmount"),
        "max_amount": data.get("maxAmount"),

        "local_min_amount": data.get("localMinAmount"),
        "local_max_amount": data.get("localMaxAmount"),

        "fixed_amounts": data.get("fixedAmounts") or [],
        "local_fixed_amounts": data.get("localFixedAmounts") or [],

        "suggested_amounts": data.get("suggestedAmounts") or [],
        "suggested_amounts_map": data.get("suggestedAmountsMap") or {},

        "raw": data,
    }


# ---------------------------
# Lookup operator
# ---------------------------

def lookup_phone_number(phone: str, country: str) -> Optional[Dict[str, Any]]:
    normalized_phone = _extract_local_number(phone)
    normalized_country = _normalize_country_iso(country)

    if not normalized_phone or not normalized_country:
        return None

    url = (
        f"{RELOADLY_BASE_URL}/operators/auto-detect/phone/"
        f"{normalized_phone}/countries/{normalized_country}"
    )

    try:
        response = _request_with_token_retry(url)

        if response.status_code != 200:
            logger.warning(
                "Reloadly lookup failed",
                extra={
                    "status_code": response.status_code,
                    "country": normalized_country,
                    "error": _extract_reloadly_error(response),  # ✅ FIX
                },
            )
            return None

        data = response.json()

        # 🔥 DEBUG SAFE
        logger.info("📡 LOOKUP RESULT OK")

        return _map_operator(data)

    except Exception as exc:
        logger.exception("Reloadly lookup exception: %s", exc)
        return None


# ---------------------------
# Get operators by country
# ---------------------------

def get_reloadly_operators_by_country(country_iso: str) -> List[Dict[str, Any]]:
    normalized_country = _normalize_country_iso(country_iso)

    if not normalized_country:
        return []

    url = (
        f"{RELOADLY_BASE_URL}/operators/countries/{normalized_country}"
        f"?includeBundles=true&includeData=true"
    )

    try:
        response = _request_with_token_retry(url)

        if response.status_code != 200:
            logger.warning(
                "Reloadly operators by country failed",
                extra={
                    "status_code": response.status_code,
                    "country_iso": normalized_country,
                    "message": _extract_reloadly_error(response),
                },
            )
            return []

        data = response.json()

        if isinstance(data, dict) and "content" in data:
            items = data.get("content") or []
        else:
            items = data or []

        return [_map_operator(item) for item in items if isinstance(item, dict)]

    except Exception as exc:
        logger.exception("Reloadly operators country exception: %s", exc)
        return []


# ---------------------------
# Get operator amounts
# ---------------------------

def get_reloadly_operator_amounts(operator_id: int) -> Dict[str, Any]:
    if not operator_id:
        return {}

    url = f"{RELOADLY_BASE_URL}/operators/{int(operator_id)}"

    try:
        response = _request_with_token_retry(url)

        if response.status_code != 200:
            logger.warning(
                "Reloadly operator details failed",
                extra={
                    "status_code": response.status_code,
                    "operator_id": operator_id,
                    "message": _extract_reloadly_error(response),
                },
            )
            return {}

        data = response.json()

        fixed_amounts = data.get("fixedAmounts") or []
        min_amount = data.get("minAmount") or data.get("localMinAmount")
        max_amount = data.get("maxAmount") or data.get("localMaxAmount")

        return {
            "denominationType": data.get("denominationType"),
            "fixedAmounts": fixed_amounts,
            "minAmount": min_amount,
            "maxAmount": max_amount,
            "localCurrency": data.get("destinationCurrencyCode")
            or data.get("localCurrency")
            or (data.get("fx") or {}).get("currencyCode"),
            "suggestedAmounts": data.get("suggestedAmounts") or [],
            "suggestedAmountsMap": data.get("suggestedAmountsMap") or {},
        }

    except Exception as exc:
        logger.exception("Reloadly operator amounts exception: %s", exc)
        return {}