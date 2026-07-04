# ---------------------------
# Feature: OTP Email Service (FINAL PRODUCTION i18n)
# ---------------------------

import json
import logging
import secrets

from services.communication.email_service import EmailService
from services.communication.otp_service import OtpService


logger = logging.getLogger(__name__)


class EmailOTPService:

    # ---------------------------
    # Config
    # ---------------------------

    OTP_LENGTH = 4

    ALLOWED_LANGUAGES = {
        "fr",
        "en",
        "ar",
        "fa",
        "ps",
        "uz",
        "tr",
        "de",
    }

    RTL_LANGUAGES = {
        "ar",
        "fa",
        "ps",
    }

    # ---------------------------
    # Blocked abusive emails
    # ---------------------------

    BLOCKED_EMAILS = {
        "kramer_n@sbcglobal.net",
        "jterryluther@hotmail.com",
        "skbook@hotmail.com",
        "bjflash@aol.com",
        "rbrenner@somersetgroup.com",
        "nfalsetto@yahoo.com",
        "s2suzuki125@gmail.com",
        "gayle.collins418@yahoo.com",
        "laketime63@hotmail.com",
        "rholmboe@telus.net",
        "lhoward1@gmail.com",
        "amoorosepang@hotmail.com",
        "masomreh@gmail.com",
    }

    # ---------------------------
    # Blocked abusive domains
    # ---------------------------

    BLOCKED_EMAIL_DOMAINS = {
        "comcast.net",
    }

    # ---------------------------
    # Helpers
    # ---------------------------

    @staticmethod
    def _safe_email(email: str) -> str:
        return str(email or "").strip().lower()

    @staticmethod
    def _safe_lang(lang: str) -> str:
        safe_lang = str(lang or "").strip().lower()

        if safe_lang not in EmailOTPService.ALLOWED_LANGUAGES:
            return "en"

        return safe_lang

    @staticmethod
    def _validate_email(email: str) -> str:
        clean_email = EmailOTPService._safe_email(email)

        if not clean_email:
            raise ValueError("invalid_email")

        if "@" not in clean_email:
            raise ValueError("invalid_email")

        local_part, domain = clean_email.rsplit("@", 1)

        if not local_part or not domain:
            raise ValueError("invalid_email")

        if clean_email in EmailOTPService.BLOCKED_EMAILS:
            logger.warning(
                "Blocked OTP email address: %s",
                clean_email,
            )
            raise ValueError("email_blocked")

        if domain in EmailOTPService.BLOCKED_EMAIL_DOMAINS:
            logger.warning(
                "Blocked OTP email domain: %s",
                domain,
            )
            raise ValueError("email_domain_blocked")

        return clean_email

    # ---------------------------
    # Generate OTP code
    # ---------------------------

    @staticmethod
    def generate_code() -> str:
        min_value = 10 ** (EmailOTPService.OTP_LENGTH - 1)
        max_value = (10 ** EmailOTPService.OTP_LENGTH) - 1

        return str(
            secrets.randbelow(
                max_value - min_value + 1
            ) + min_value
        )

    # ---------------------------
    # Load translations
    # ---------------------------

    @staticmethod
    def _load_l10n(lang: str):
        safe_lang = EmailOTPService._safe_lang(lang)

        try:
            with open(
                f"l10n/{safe_lang}.json",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except Exception as exc:
            logger.warning(
                "Unable to load l10n/%s.json: %s",
                safe_lang,
                exc,
            )

            try:
                with open(
                    "l10n/en.json",
                    encoding="utf-8",
                ) as file:
                    return json.load(file)

            except Exception:
                with open(
                    "l10n/fr.json",
                    encoding="utf-8",
                ) as file:
                    return json.load(file)

    # ---------------------------
    # Send verification email
    # ---------------------------

    @staticmethod
    def send_verification(
        email: str,
        lang: str = "en",
    ) -> str:
        clean_email = EmailOTPService._validate_email(email)
        safe_lang = EmailOTPService._safe_lang(lang)

        # ---------------------------
        # Generate OTP
        # ---------------------------

        code = EmailOTPService.generate_code()

        # ---------------------------
        # Store OTP
        # ---------------------------

        OtpService.store_otp(
            "email",
            clean_email,
            code,
        )

        # ---------------------------
        # Traduction
        # ---------------------------

        l10n = EmailOTPService._load_l10n(
            safe_lang,
        )

        def t(key: str, default: str = "") -> str:
            current = l10n

            for part in key.split("."):
                if (
                    not isinstance(current, dict)
                    or part not in current
                ):
                    return default or key

                current = current[part]

            if isinstance(current, str):
                return current

            return default or key

        dir_attr = (
            "rtl"
            if safe_lang in EmailOTPService.RTL_LANGUAGES
            else "ltr"
        )

        text_align = (
            "right"
            if safe_lang in EmailOTPService.RTL_LANGUAGES
            else "center"
        )

        # ---------------------------
        # Texte i18n
        # ---------------------------

        subject = t(
            "auth.otp_title",
            "Verification code",
        )

        title = t(
            "auth.otp_title",
            "Verification code",
        )

        subtitle = t(
            "auth.security_hint",
            "One-time code",
        )

        expire = t(
            "auth.otp_help",
            "This code expires in 5 minutes",
        )

        # ---------------------------
        # HTML
        # ---------------------------

        html = f"""
<table
  width="100%"
  cellpadding="0"
  cellspacing="0"
  style="background:#f5f5f5;padding:20px;"
  dir="{dir_attr}"
>
  <tr>
    <td align="center">

      <table
        width="400"
        cellpadding="0"
        cellspacing="0"
        style="
          background:#ffffff;
          border-radius:12px;
          padding:24px;
          text-align:{text_align};
          font-family:Arial,sans-serif;
        "
      >

        <tr>
          <td
            style="
              font-size:20px;
              font-weight:600;
              color:#111;
              text-align:center;
            "
          >
            Yeslek
          </td>
        </tr>

        <tr>
          <td
            style="
              padding-top:12px;
              font-size:16px;
              font-weight:600;
              color:#111;
            "
          >
            {title}
          </td>
        </tr>

        <tr>
          <td
            style="
              padding-top:8px;
              font-size:14px;
              color:#666;
            "
          >
            {subtitle}
          </td>
        </tr>

        <tr>
          <td
            style="
              padding:24px 0;
              text-align:center;
            "
          >
            <span
              style="
                font-size:34px;
                font-weight:700;
                letter-spacing:6px;
                color:#000;
              "
            >
              {code}
            </span>
          </td>
        </tr>

        <tr>
          <td
            style="
              font-size:12px;
              color:#999;
            "
          >
            {expire}
          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>
"""

        # ---------------------------
        # Text i18n
        # ---------------------------

        text_messages = {
            "fr": (
                f"Votre code Yeslek est : {code}\n"
                "Expire dans 5 minutes."
            ),

            "en": (
                f"Your Yeslek code is: {code}\n"
                "Expires in 5 minutes."
            ),

            "tr": (
                f"Yeslek doğrulama kodunuz: {code}\n"
                "5 dakika içinde geçerlidir."
            ),

            "de": (
                f"Ihr Yeslek-Code lautet: {code}\n"
                "Läuft in 5 Minuten ab."
            ),

            "ar": (
                f"رمز التحقق الخاص بك: {code}\n"
                "ينتهي خلال 5 دقائق."
            ),

            "fa": (
                f"کد تأیید شما: {code}\n"
                "تا ۵ دقیقه معتبر است."
            ),

            "ps": (
                f"ستاسو کوډ: {code}\n"
                "په ۵ دقیقو کې پای ته رسیږي."
            ),

            "uz": (
                f"Sizning tasdiqlash kodingiz: {code}\n"
                "5 daqiqa ichida amal qiladi."
            ),
        }

        text = text_messages.get(
            safe_lang,
            text_messages["en"],
        )

        # ---------------------------
        # Send email
        # ---------------------------

        sent = EmailService.send_email(
            to_email=clean_email,
            subject=subject,
            html=html,
            text=text,
        )

        if sent is False:
            logger.error(
                "OTP email not sent to %s",
                clean_email,
            )
            raise RuntimeError("email_send_failed")

        logger.info(
            "OTP email sent to %s",
            clean_email,
        )

        return code