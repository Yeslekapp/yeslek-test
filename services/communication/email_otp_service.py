# ---------------------------
# Feature: OTP Email Service (FINAL PRODUCTION i18n)
# ---------------------------

import secrets
import json
import os
from services.communication.email_service import EmailService
from services.communication.otp_service import OtpService


class EmailOTPService:

    # ---------------------------
    # Generate OTP code
    # ---------------------------
    @staticmethod
    def generate_code() -> str:
        return str(secrets.randbelow(9000) + 1000)

    # ---------------------------
    # Load translations
    # ---------------------------
    @staticmethod
    def _load_l10n(lang: str):
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
    # Send verification email
    # ---------------------------
    @staticmethod
    def send_verification(email: str, lang: str = "fr"):

        code = EmailOTPService.generate_code()

        # 🔐 store OTP
        OtpService.store_otp("email", email, code)

        # ---------------------------
        # Traduction
        # ---------------------------
        l10n = EmailOTPService._load_l10n(lang)

        def t(key, default=""):
            cur = l10n
            for p in key.split("."):
                if not isinstance(cur, dict) or p not in cur:
                    return default or key
                cur = cur[p]
            return cur if isinstance(cur, str) else default

        rtl_langs = {"ar", "fa", "ps"}
        dir_attr = "rtl" if lang in rtl_langs else "ltr"
        text_align = "right" if lang in rtl_langs else "center"

        # ---------------------------
        # Texte i18n
        # ---------------------------
        subject = t("auth.otp_title", "Verification code")

        title = t("auth.otp_title", "Verification code")
        subtitle = t("auth.security_hint", "One-time code")
        expire = t("auth.otp_help", "This code expires in 5 minutes")

        # ---------------------------
        # HTML
        # ---------------------------
        html = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px;" dir="{dir_attr}">
  <tr>
    <td align="center">

      <table width="400" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:24px;text-align:{text_align};font-family:Arial,sans-serif;">

        <tr>
          <td style="font-size:20px;font-weight:600;color:#111;text-align:center;">
            Yeslek
          </td>
        </tr>

        <tr>
          <td style="padding-top:12px;font-size:16px;font-weight:600;color:#111;">
            {title}
          </td>
        </tr>

        <tr>
          <td style="padding-top:8px;font-size:14px;color:#666;">
            {subtitle}
          </td>
        </tr>

        <tr>
          <td style="padding:24px 0;text-align:center;">
            <span style="font-size:34px;font-weight:700;letter-spacing:6px;color:#000;">
              {code}
            </span>
          </td>
        </tr>

        <tr>
          <td style="font-size:12px;color:#999;">
            {expire}
          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>
"""

        # ---------------------------
        # TEXT (iOS autofill + i18n)
        # ---------------------------
        text_messages = {
            "fr": f"Votre code Yeslek est : {code}\nExpire dans 5 minutes.",
            "en": f"Your Yeslek code is: {code}\nExpires in 5 minutes.",
            "tr": f"Yeslek doğrulama kodunuz: {code}\n5 dakika içinde geçerlidir.",
            "ar": f"رمز التحقق الخاص بك: {code}\nينتهي خلال 5 دقائق.",
            "fa": f"کد تأیید شما: {code}\nتا ۵ دقیقه معتبر است.",
            "ps": f"ستاسو کوډ: {code}\nپه ۵ دقیقو کې پای ته رسیږي.",
            "uz": f"Sizning tasdiqlash kodingiz: {code}\n5 daqiqa ichida amal qiladi."
        }

        text = text_messages.get(lang, text_messages["en"])

        EmailService.send_email(
            to_email=email,
            subject=subject,
            html=html,
            text=text
        )

        return code