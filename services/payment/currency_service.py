# ---------------------------
# Feature: Currency Service
# ---------------------------

from __future__ import annotations


class CurrencyService:
    PREFIX_TO_CURRENCY = {
    # --- AFRIQUE ---
    "+211": "SSP", "+212": "MAD", "+213": "DZD", "+216": "TND", "+218": "LYD",
    "+220": "GMD", "+221": "XOF", "+222": "MRU", "+223": "XOF", "+224": "GNF",
    "+225": "XOF", "+226": "XOF", "+227": "XOF", "+228": "XOF", "+229": "XOF",
    "+230": "MUR", "+231": "LRD", "+232": "SLL", "+233": "GHS", "+234": "NGN",
    "+235": "XAF", "+236": "XAF", "+237": "XAF", "+238": "CVE", "+239": "STN",
    "+240": "XAF", "+241": "XAF", "+242": "XAF", "+243": "CDF", "+244": "AOA",
    "+245": "XOF", "+248": "SCR", "+249": "SDG", "+250": "RWF", "+251": "ETB",
    "+252": "SOS", "+253": "DJF", "+254": "KES", "+255": "TZS", "+256": "UGX",
    "+257": "BIF", "+258": "MZN", "+260": "ZMW", "+261": "MGA", "+262": "EUR",
    "+263": "ZWL", "+264": "NAD", "+265": "MWK", "+266": "LSL", "+267": "BWP",
    "+268": "SZL", "+269": "KMF", "+27": "ZAR",

    # --- EUROPE ---
    "+30": "EUR", "+31": "EUR", "+32": "EUR", "+33": "EUR", "+34": "EUR",
    "+36": "HUF", "+39": "EUR", "+40": "RON", "+41": "CHF", "+43": "EUR",
    "+44": "GBP", "+45": "DKK", "+46": "SEK", "+47": "NOK", "+48": "PLN",
    "+49": "EUR", "+350": "GIP", "+351": "EUR", "+352": "EUR", "+353": "EUR",
    "+354": "ISK", "+355": "ALL", "+356": "EUR", "+357": "EUR", "+358": "EUR",
    "+359": "BGN", "+370": "EUR", "+371": "EUR", "+372": "EUR", "+373": "MDL",
    "+374": "AMD", "+375": "BYN", "+376": "EUR", "+377": "EUR", "+378": "EUR",
    "+380": "UAH", "+381": "RSD", "+382": "EUR", "+383": "EUR", "+385": "EUR",
    "+386": "EUR", "+387": "BAM", "+389": "MKD",

    # --- ASIE & MOYEN-ORIENT ---
    "+7": "RUB", "+90": "TRY", "+91": "INR", "+92": "PKR", "+93": "AFN",
    "+94": "LKR", "+95": "MMK", "+98": "IRR", "+81": "JPY", "+82": "KRW",
    "+84": "VND", "+86": "CNY", "+960": "MVR", "+961": "LBP", "+962": "JOD",
    "+963": "SYP", "+964": "IQD", "+965": "KWD", "+966": "SAR", "+967": "YER",
    "+968": "OMR", "+970": "ILS", "+971": "AED", "+972": "ILS", "+973": "BHD",
    "+974": "QAR", "+975": "BTN", "+976": "MNT", "+977": "NPR",

    # --- AMÉRIQUES ---
    "+1": "USD",  # fallback global (USA + autres)
    "+51": "PEN", "+52": "MXN", "+53": "CUP", "+54": "ARS",
    "+55": "BRL", "+56": "CLP", "+57": "COP", "+58": "VES",
    "+501": "BZD", "+502": "GTQ", "+503": "SVC", "+504": "HNL",
    "+505": "NIO", "+506": "CRC", "+507": "PAB",
    "+509": "HTG", "+591": "BOB", "+592": "GYD",
    "+593": "USD", "+595": "PYG", "+597": "SRD",
    "+598": "UYU",

    # --- OCÉANIE ---
    "+60": "MYR", "+61": "AUD", "+62": "IDR", "+63": "PHP", "+64": "NZD",
    "+65": "SGD", "+66": "THB", "+670": "USD", "+673": "BND", "+674": "AUD",
    "+675": "PGK", "+676": "TOP", "+677": "SBD", "+678": "VUV", "+679": "FJD",
    "+680": "USD", "+682": "NZD", "+685": "WST",
}

    # ---------------------------
    # UI / Stripe only
    # ---------------------------
    @staticmethod
    def currency_from_phone(phone: str) -> str:
        if not phone:
            return "EUR"

        value = str(phone).strip()

        for prefix in sorted(CurrencyService.PREFIX_TO_CURRENCY.keys(), key=len, reverse=True):
            if value.startswith(prefix):
                return CurrencyService.PREFIX_TO_CURRENCY[prefix]

        return "EUR"

    # ---------------------------
    # Display received value
    # ---------------------------
    @staticmethod
    def received_display_value(phone, amount, selected_forfait, quote):
        if selected_forfait and selected_forfait.get("gb"):
            return f"{selected_forfait['gb']} GB"

        if not quote:
            return "—"

        try:
            destination_amount = quote.get("destinationAmount")
            destination_currency = quote.get("destinationCurrencyCode")

            if destination_amount is not None and destination_currency:
                return f"{CurrencyService._format_amount(destination_amount)} {destination_currency}"

            local_amount = quote.get("localAmount")
            local_currency = quote.get("localCurrency")

            if local_amount is not None and local_currency:
                return f"{CurrencyService._format_amount(local_amount)} {local_currency}"

        except Exception:
            return "—"

        return "—"

    # ---------------------------
    # Internal helper
    # ---------------------------
    @staticmethod
    def _format_amount(value):
        try:
            value = float(value)
            if value.is_integer():
                return str(int(value))
            return f"{value:.2f}".rstrip("0").rstrip(".")
        except Exception:
            return "0"
        
        # ---------------------------
# Feature: LIVE FX conversion
# ---------------------------

import requests

def convert_live(amount: float, to_currency: str) -> float:
    try:
        url = f"https://api.exchangerate.host/convert?from=EUR&to={to_currency}&amount={amount}"
        res = requests.get(url, timeout=3)
        data = res.json()

        return round(data.get("result", amount), 2)

    except Exception:
        # fallback sécurité
        return amount