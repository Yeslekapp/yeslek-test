# ---------------------------
# Email Service (Brevo)
# ---------------------------

import os
from datetime import datetime
import requests


class EmailService:

    # ---------------------------
    # Brevo config
    # ---------------------------
    API_KEY = os.getenv("BREVO_API_KEY")
    FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
    FROM_NAME = os.getenv("BREVO_FROM_NAME", "Yeslek")

    BASE_URL = "https://api.brevo.com/v3/smtp/email"

    # ---------------------------
    # Generic email sender
    # ---------------------------
    @staticmethod
    def send_email(to_email: str, subject: str, html: str, text: str = ""):

        if not EmailService.API_KEY or not EmailService.FROM_EMAIL:
            print("⚠️ Email skipped: missing Brevo config")
            return False

        try:
            headers = {
                "accept": "application/json",
                "api-key": EmailService.API_KEY,
                "content-type": "application/json"
            }

            payload = {
                "sender": {
                    "name": EmailService.FROM_NAME,
                    "email": EmailService.FROM_EMAIL
                },
                "to": [
                    {"email": to_email}
                ],
                "subject": subject,
                "htmlContent": html,
                "textContent": text or "Yeslek notification"
            }

            response = requests.post(
                EmailService.BASE_URL,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code >= 300:
                print("❌ Brevo error:", response.text)
                return False

            return True

        except Exception as e:
            print("❌ Brevo email error:", e)
            return False

    # ---------------------------
    # Load translations (NEW)
    # ---------------------------
    @staticmethod
    def _load_l10n(lang: str):
        import json

        allowed = {
            "fr",
            "en",
            "ar",
            "fa",
            "ps",
            "uz",
            "tr",
            "de",
        }

        lang = str(lang or "en").lower().strip()

        if lang not in allowed:
            lang = "en"

        try:
            with open(f"l10n/{lang}.json", encoding="utf-8") as f:
                return json.load(f)

        except Exception:
            with open("l10n/en.json", encoding="utf-8") as f:
                return json.load(f)

    # ---------------------------
    # Helpers
    # ---------------------------
    @staticmethod
    def _country_flag(iso: str | None) -> str:
        try:
            if not iso or len(iso) != 2:
                return ""
            return "".join(chr(127397 + ord(c)) for c in iso.upper())
        except Exception:
            return ""

    # ---------------------------
    # Payment success email
    # ---------------------------
    @staticmethod
    def send_payment_success(
        email: str,
        payload: dict,
        lang: str = "en",  # ✅ AJOUT
        phone: str | None = None,
        country_name: str | None = None,
        operator_name: str | None = None,
        operator_logo: str | None = None
    ):

        # ---------------------------
        # Traduction / language
        # ---------------------------
        allowed_langs = {
            "fr",
            "en",
            "ar",
            "fa",
            "ps",
            "uz",
            "tr",
            "de",
        }

        lang = str(
            lang
            or payload.get("lang")
            or payload.get("locale")
            or "en"
        ).lower().strip()

        if lang not in allowed_langs:
            lang = "en"

        l10n = EmailService._load_l10n(lang)

        def t(key, default=""):
            cur = l10n
            for p in key.split("."):
                if not isinstance(cur, dict) or p not in cur:
                    return default or key
                cur = cur[p]
            return cur if isinstance(cur, str) else default

        rtl_langs = {"ar", "fa", "ps"}
        dir_attr = "rtl" if lang in rtl_langs else "ltr"

        # ---------------------------
        # Data (SAFE + PRO)
        # ---------------------------
        forfait = payload.get("forfait")

        amount = payload.get("amount") or 0
        charged_amount = payload.get("charged_amount") or amount or 0

        reference = payload.get("reference")
        date = payload.get("date")

        fee = round(charged_amount - amount, 2)
        total = charged_amount

        country_display = country_name or "-"
        operator_display = operator_name or "-"

        flag = EmailService._country_flag(country_name)

        logo_html = ""
        if operator_logo:
            logo_html = f'<img src="{operator_logo}" style="height:16px;vertical-align:middle;margin-left:6px;">'

        year = datetime.now().year

        # ---------------------------
        # Subject (FIX LANG)
        # ---------------------------
        subject = f"{t('payment.success.title')} - {reference}"

        # ---------------------------
        # HTML (IDENTIQUE + t())
        # ---------------------------
        labels = {
            "fr": {
                "country": "Pays",
                "operator": "Opérateur",
                "product": "Produit",
                "fees": "Frais",
                "total_paid": "Total payé",
                "phone": "Téléphone",
                "date": "Date",
                "reference": "Référence",
                "paid": "Montant",
                "button": "Continuer",
                "message": "Votre paiement a été confirmé.",
                "mobile_topup": "Recharge mobile",
            },
            "en": {
                "country": "Country",
                "operator": "Operator",
                "product": "Product",
                "fees": "Fees",
                "total_paid": "Total paid",
                "phone": "Phone",
                "date": "Date",
                "reference": "Reference",
                "paid": "Amount",
                "button": "Continue",
                "message": "Your payment has been confirmed.",
                "mobile_topup": "Mobile top-up",
            },
            "ar": {
                "country": "البلد",
                "operator": "المشغل",
                "product": "المنتج",
                "fees": "الرسوم",
                "total_paid": "إجمالي المدفوع",
                "phone": "الهاتف",
                "date": "التاريخ",
                "reference": "المرجع",
                "paid": "المبلغ",
                "button": "متابعة",
                "message": "تم تأكيد الدفع الخاص بك.",
                "mobile_topup": "شحن الهاتف",
            },
            "fa": {
                "country": "کشور",
                "operator": "اپراتور",
                "product": "محصول",
                "fees": "هزینه",
                "total_paid": "مجموع پرداختی",
                "phone": "تلفن",
                "date": "تاریخ",
                "reference": "مرجع",
                "paid": "مبلغ",
                "button": "پرداخت",
                "message": "پرداخت شما تأیید شد.",
                "mobile_topup": "شارژ موبایل",
            },
            "ps": {
                "country": "هېواد",
                "operator": "آپریټر",
                "product": "محصول",
                "fees": "فیس",
                "total_paid": "ټول تادیه شوي",
                "phone": "تلیفون",
                "date": "نېټه",
                "reference": "مرجع",
                "paid": "مبلغ",
                "button": "ادامه",
                "message": "ستاسو تادیه تایید شوه.",
                "mobile_topup": "موبایل چارج",
            },
            "tr": {
                "country": "Ülke",
                "operator": "Operatör",
                "product": "Ürün",
                "fees": "Ücretler",
                "total_paid": "Toplam ödenen",
                "phone": "Telefon",
                "date": "Tarih",
                "reference": "Referans",
                "paid": "Tutar",
                "button": "Devam et",
                "message": "Ödemeniz onaylandı.",
                "mobile_topup": "Mobil yükleme",
            },
            "de": {
                "country": "Land",
                "operator": "Betreiber",
                "product": "Produkt",
                "fees": "Gebühren",
                "total_paid": "Gesamt bezahlt",
                "phone": "Telefon",
                "date": "Datum",
                "reference": "Referenz",
                "paid": "Betrag",
                "button": "Weiter",
                "message": "Ihre Zahlung wurde bestätigt.",
                "mobile_topup": "Handy-Aufladung",
            },
        }

        L = labels.get(lang, labels["en"])

        product_display = forfait if forfait else L["mobile_topup"]

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>

<body dir="{dir_attr}" style="margin:0;background:#0e1117;font-family:Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#0e1117;padding:16px 8px;">
<tr>
<td align="center">

<table width="100%" cellpadding="0" cellspacing="0"
style="max-width:560px;width:100%;background:#111827;border-radius:16px;padding:22px;color:white;box-sizing:border-box;">

<tr>
<td style="font-size:30px;font-weight:bold;color:#00d1c1;text-align:left;" dir="ltr">
Yeslek
</td>

<td style="font-size:13px;color:#9ca3af;text-align:right;white-space:nowrap;" dir="ltr">
{L["reference"]}: {reference or "-"}
</td>
</tr>

<tr><td colspan="2" style="height:28px"></td></tr>

<tr>
<td colspan="2" style="font-size:24px;font-weight:bold;text-align:center;color:#ffffff;">
{t("payment.success.title", "Payment successful")}
</td>
</tr>

<tr>
<td colspan="2" style="text-align:center;color:#9ca3af;padding-top:8px;font-size:15px;">
{L["message"]}
</td>
</tr>

<tr><td colspan="2" style="height:28px"></td></tr>

<tr>
<td colspan="2">

<table width="100%" cellpadding="0" cellspacing="0"
style="background:#0f172a;border-radius:14px;padding:18px;width:100%;box-sizing:border-box;">

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;width:42%;">
{L["date"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;width:58%;white-space:nowrap;" dir="ltr">
{date or "-"}
</td>
</tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["phone"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;white-space:nowrap;" dir="ltr">
{phone or "-"}
</td>
</tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["country"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;" dir="ltr">
{flag} {country_display}
</td>
</tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["operator"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;">
{operator_display} {logo_html}
</td>
</tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["product"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;">
{product_display}
</td>
</tr>

<tr><td colspan="2" style="height:14px"></td></tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["paid"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;white-space:nowrap;" dir="ltr">
{amount:.2f} €
</td>
</tr>

<tr>
<td style="color:#9ca3af;font-size:14px;padding:7px 0;">
{L["fees"]}:
</td>
<td style="text-align:right;color:#ffffff;font-size:15px;padding:7px 0;white-space:nowrap;" dir="ltr">
{fee:.2f} €
</td>
</tr>

<tr><td colspan="2" style="height:12px;border-bottom:1px solid #1f2937;"></td></tr>
<tr><td colspan="2" style="height:12px;"></td></tr>

<tr>
<td style="font-weight:bold;color:#ffffff;font-size:16px;padding:7px 0;">
{L["total_paid"]}:
</td>
<td style="text-align:right;font-weight:bold;font-size:20px;color:#00d1c1;padding:7px 0;white-space:nowrap;" dir="ltr">
{total:.2f} €
</td>
</tr>

</table>

</td>
</tr>

<tr><td colspan="2" style="height:28px"></td></tr>

<tr>
<td colspan="2" align="center">

<a href="https://yeslek.com"
style="background:#b4ff00;color:black;padding:14px 34px;text-decoration:none;border-radius:30px;font-weight:bold;display:inline-block;">
{L["button"]}
</a>

</td>
</tr>

<tr><td colspan="2" style="height:24px"></td></tr>

<tr>
<td colspan="2" style="text-align:center;color:#9ca3af;font-size:12px;">
support@yeslek.com
</td>
</tr>

<tr>
<td colspan="2" style="text-align:center;color:#6b7280;font-size:11px;padding-top:10px;">
© {year} Yeslek
</td>
</tr>

</table>

</td>
</tr>
</table>

</body>
</html>
"""

        return EmailService.send_email(
            to_email=email,
            subject=subject,
            html=html
        )