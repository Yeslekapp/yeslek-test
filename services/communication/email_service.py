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

        allowed = {"fr", "en", "ar", "fa", "ps", "uz", "tr"}

        if lang not in allowed:
            lang = "fr"

        try:
            with open(f"l10n/{lang}.json", encoding="utf-8") as f:
                return json.load(f)
        except:
            with open("l10n/fr.json", encoding="utf-8") as f:
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
        lang: str = "fr",  # ✅ AJOUT
        phone: str | None = None,
        country_name: str | None = None,
        operator_name: str | None = None,
        operator_logo: str | None = None
    ):

        # ---------------------------
        # Traduction (NEW)
        # ---------------------------
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
        charged_amount = payload.get("charged_amount") or amount
        credit_used = payload.get("credit_used") or 0

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
        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>

<body dir="{dir_attr}" style="margin:0;background:#0e1117;font-family:Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 0;">
<tr>
<td align="center">

<table width="100%" cellpadding="0" cellspacing="0"
style="max-width:520px;background:#111827;border-radius:14px;padding:30px;color:white;">

<tr>
<td style="font-size:28px;font-weight:bold;color:#00d1c1;">
Yeslek
</td>

<td style="text-align:right;font-size:13px;color:#9ca3af;">
{t("payment.success.referenceLabel")} : {reference}
</td>
</tr>

<tr><td colspan="2" style="height:25px"></td></tr>

<tr>
<td colspan="2" style="font-size:22px;font-weight:bold;text-align:center;">
{t("payment.success.title")}
</td>
</tr>

<tr>
<td colspan="2" style="text-align:center;color:#9ca3af;padding-top:6px;">
{t("payment.success.message")}
</td>
</tr>

<tr><td colspan="2" style="height:30px"></td></tr>

<tr>
<td colspan="2">

<table width="100%" style="background:#0f172a;border-radius:12px;padding:20px;">

<tr>
<td style="color:#9ca3af;">{t("payment.success.dateLabel")} :</td>
<td style="text-align:right;">{date or "-"}</td>
</tr>

<tr><td style="height:8px"></td></tr>

<tr>
<td style="color:#9ca3af;">{t("profile.phone")} :</td>
<td style="text-align:right;">{phone or "-"}</td>
</tr>

<tr><td style="height:8px"></td></tr>

<tr>
<td style="color:#9ca3af;">Pays :</td>
<td style="text-align:right;">{flag} {country_display}</td>
</tr>

<tr><td style="height:8px"></td></tr>

<tr>
<td style="color:#9ca3af;">Opérateur :</td>
<td style="text-align:right;">
{operator_display} {logo_html}
</td>
</tr>

<tr><td style="height:8px"></td></tr>

<tr>
<td style="color:#9ca3af;">Produit :</td>
<td style="text-align:right;">
{forfait if forfait else "Recharge mobile"}
</td>
</tr>

<tr><td style="height:20px"></td></tr>

<tr>
<td style="color:#9ca3af;">{t("payment.success.amountLabel")} :</td>
<td style="text-align:right;">{amount:.2f} €</td>
</tr>

<tr><td style="height:6px"></td></tr>

<tr>
<td style="color:#9ca3af;">Frais :</td>
<td style="text-align:right;">{fee:.2f} €</td>
</tr>

<tr><td style="height:6px"></td></tr>

<tr>
<td style="color:#9ca3af;">Crédit utilisé :</td>
<td style="text-align:right;">-{credit_used:.2f} €</td>
</tr>

<tr><td style="height:10px"></td></tr>

<tr>
<td style="font-weight:bold;">Total payé :</td>
<td style="text-align:right;font-weight:bold;font-size:18px;color:#00d1c1;">
{total:.2f} €
</td>
</tr>

</table>

</td>
</tr>

<tr><td colspan="2" style="height:30px"></td></tr>

<tr>
<td colspan="2" align="center">

<a href="https://yeslek.com"
style="background:#b4ff00;color:black;padding:14px 26px;
text-decoration:none;border-radius:30px;font-weight:bold;display:inline-block;">
{t("recharge.selectAmount.goToPay")}
</a>

</td>
</tr>

<tr><td colspan="2" style="height:25px"></td></tr>

<tr>
<td colspan="2" style="text-align:center;color:#9ca3af;font-size:12px;">
support@yeslek.com
</td>
</tr>

<tr>
<td colspan="2" style="text-align:center;color:#6b7280;font-size:11px;padding-top:10px;">
© {year} yeslek
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