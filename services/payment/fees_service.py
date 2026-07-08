# ---------------------------
# Feature: Fees Service
# ---------------------------

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


class FeesService:
    """
    Modèle MARKUP :
    - le client paie montant + frais
    - le payout envoyé à Reloadly reste le montant net métier
    """

    DEFAULT_RATE = Decimal("0.20")

    CURRENCY_FEES = {
    # ---------------------------
    # Afrique
    # ---------------------------
    "SSP": Decimal("0.23"),
    "MAD": Decimal("0.22"),
    "DZD": Decimal("0.22"),
    "TND": Decimal("0.22"),
    "LYD": Decimal("0.22"),
    "GMD": Decimal("0.22"),
    "XOF": Decimal("0.20"),
    "MRU": Decimal("0.22"),
    "GNF": Decimal("0.23"),
    "MUR": Decimal("0.20"),
    "LRD": Decimal("0.23"),
    "SLL": Decimal("0.23"),
    "GHS": Decimal("0.22"),
    "NGN": Decimal("0.99"),
    "XAF": Decimal("0.20"),
    "CVE": Decimal("0.22"),
    "STN": Decimal("0.22"),
    "CDF": Decimal("0.23"),
    "AOA": Decimal("0.23"),
    "SCR": Decimal("0.20"),
    "SDG": Decimal("0.25"),
    "RWF": Decimal("0.22"),
    "ETB": Decimal("0.23"),
    "SOS": Decimal("0.25"),
    "DJF": Decimal("0.22"),
    "KES": Decimal("0.22"),
    "TZS": Decimal("0.22"),
    "UGX": Decimal("0.22"),
    "BIF": Decimal("0.23"),
    "MZN": Decimal("0.23"),
    "ZMW": Decimal("0.22"),
    "MGA": Decimal("0.23"),
    "EUR": Decimal("0.18"),   # +262 / territoires en EUR
    "ZWL": Decimal("0.25"),
    "NAD": Decimal("0.22"),
    "MWK": Decimal("0.23"),
    "LSL": Decimal("0.22"),
    "BWP": Decimal("0.22"),
    "SZL": Decimal("0.22"),
    "KMF": Decimal("0.23"),
    "ZAR": Decimal("0.22"),
    "SHP": Decimal("0.20"),
    "ERN": Decimal("0.23"),
    "AWG": Decimal("0.20"),

    # ---------------------------
    # Europe
    # ---------------------------
    "GBP": Decimal("0.18"),
    "HUF": Decimal("0.20"),
    "RON": Decimal("0.20"),
    "CHF": Decimal("0.18"),
    "DKK": Decimal("0.18"),
    "SEK": Decimal("0.18"),
    "NOK": Decimal("0.18"),
    "PLN": Decimal("0.20"),
    "GIP": Decimal("0.20"),
    "ISK": Decimal("0.20"),
    "ALL": Decimal("0.20"),
    "BGN": Decimal("0.20"),
    "MDL": Decimal("0.22"),
    "AMD": Decimal("0.22"),
    "BYN": Decimal("0.22"),
    "UAH": Decimal("0.22"),
    "RSD": Decimal("0.22"),
    "BAM": Decimal("0.22"),
    "MKD": Decimal("0.22"),

    # ---------------------------
    # Asie & Moyen-Orient
    # ---------------------------
    "RUB": Decimal("0.22"),
    "TRY": Decimal("0.20"),
    "INR": Decimal("0.22"),
    "PKR": Decimal("0.23"),
    "AFN": Decimal("0.32"),
    "LKR": Decimal("0.22"),
    "MMK": Decimal("0.23"),
    "IRR": Decimal("0.25"),
    "JPY": Decimal("0.18"),
    "KRW": Decimal("0.20"),
    "VND": Decimal("0.23"),
    "CNY": Decimal("0.20"),
    "MVR": Decimal("0.20"),
    "LBP": Decimal("0.25"),
    "JOD": Decimal("0.20"),
    "SYP": Decimal("0.25"),
    "IQD": Decimal("0.23"),
    "KWD": Decimal("0.18"),
    "SAR": Decimal("0.18"),
    "YER": Decimal("0.25"),
    "OMR": Decimal("0.18"),
    "ILS": Decimal("0.18"),
    "AED": Decimal("0.18"),
    "BHD": Decimal("0.18"),
    "QAR": Decimal("0.18"),
    "BTN": Decimal("0.22"),
    "MNT": Decimal("0.22"),
    "NPR": Decimal("0.22"),

    # ---------------------------
    # Amériques
    # ---------------------------
    "USD": Decimal("0.18"),
    "PEN": Decimal("0.22"),
    "MXN": Decimal("0.20"),
    "CUP": Decimal("0.23"),
    "ARS": Decimal("0.25"),
    "BRL": Decimal("0.22"),
    "CLP": Decimal("0.22"),
    "COP": Decimal("0.22"),
    "VES": Decimal("0.25"),
    "BZD": Decimal("0.20"),
    "GTQ": Decimal("0.22"),
    "SVC": Decimal("0.20"),
    "HNL": Decimal("0.22"),
    "NIO": Decimal("0.22"),
    "CRC": Decimal("0.20"),
    "PAB": Decimal("0.18"),
    "HTG": Decimal("0.23"),
    "BOB": Decimal("0.22"),
    "GYD": Decimal("0.22"),
    "PYG": Decimal("0.22"),
    "SRD": Decimal("0.23"),
    "UYU": Decimal("0.20"),
    "ANG": Decimal("0.20"),

    # ---------------------------
    # Océanie
    # ---------------------------
    "MYR": Decimal("0.20"),
    "AUD": Decimal("0.18"),
    "IDR": Decimal("0.23"),
    "PHP": Decimal("0.22"),
    "NZD": Decimal("0.18"),
    "SGD": Decimal("0.18"),
    "THB": Decimal("0.22"),
    "BND": Decimal("0.18"),
    "PGK": Decimal("0.22"),
    "TOP": Decimal("0.20"),
    "SBD": Decimal("0.22"),
    "VUV": Decimal("0.22"),
    "FJD": Decimal("0.20"),
    "XPF": Decimal("0.20"),
    "WST": Decimal("0.20"),
}

    MIN_FEE = Decimal("0.20")

    # ---------------------------
    # Helpers
    # ---------------------------
    @staticmethod
    def _to_decimal(value) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def _round(value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # ---------------------------
    # Get fee rate
    # ---------------------------
    @classmethod
    def get_tax_rate(cls, currency: str) -> float:
        if not currency:
            return float(cls.DEFAULT_RATE)

        return float(cls.CURRENCY_FEES.get(currency.upper(), cls.DEFAULT_RATE))

    # ---------------------------
    # Compute fee
    # ---------------------------
    @classmethod
    def compute_fee(cls, amount: float, rate: float) -> float:
        amount_dec = cls._to_decimal(amount)
        rate_dec = cls._to_decimal(rate)

        if amount_dec <= 0:
            return 0.0

        fee = cls._round(amount_dec * rate_dec)
        fee = max(fee, cls.MIN_FEE)

        return float(cls._round(fee))

    # ---------------------------
    # Backward compat
    # ---------------------------
    @staticmethod
    def compute_tax(amount: float, rate: float) -> float:
        return FeesService.compute_fee(amount, rate)

    # ---------------------------
    # Compute total
    # ---------------------------
    @classmethod
    def compute_total(cls, amount: float, rate: float) -> float:
        amount_dec = cls._to_decimal(amount)

        if amount_dec <= 0:
            return 0.0

        fee = cls._to_decimal(cls.compute_fee(float(amount_dec), rate))
        total = cls._round(amount_dec + fee)

        return float(total)

    # ---------------------------
    # Breakdown
    # ---------------------------
    @classmethod
    def breakdown(cls, amount: float, currency: str) -> dict:
        amount_dec = cls._to_decimal(amount)
        rate = cls.get_tax_rate(currency)
        fee = cls.compute_fee(float(amount_dec), rate)
        total = cls.compute_total(float(amount_dec), rate)

        return {
            "amount": float(cls._round(amount_dec)),
            "tax_rate": rate,
            "tax": fee,
            "total": total,
        }

    # ---------------------------
    # Compute payout
    # ---------------------------
    @classmethod
    def compute_payout(cls, amount: float, currency: str) -> dict:
        amount_dec = cls._to_decimal(amount)

        if amount_dec <= 0:
            return {
                "paid": 0.0,
                "fee": 0.0,
                "payout": 0.0,
                "rate": 0.0,
            }

        rate = cls.get_tax_rate(currency)
        fee = cls.compute_fee(float(amount_dec), rate)
        total = cls.compute_total(float(amount_dec), rate)

        return {
            "paid": total,
            "fee": fee,
            "payout": float(cls._round(amount_dec)),
            "rate": rate,
        }