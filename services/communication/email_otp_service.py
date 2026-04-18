# ---------------------------
# Feature: OTP Email Service (FINAL PRODUCTION iOS SAFE)
# ---------------------------

import secrets
from services.communication.email_service import EmailService
from services.communication.otp_service import OtpService


class EmailOTPService:

    # ---------------------------
    # Generate OTP code (6 chiffres sécurisé)
    # ---------------------------
    @staticmethod
    def generate_code() -> str:
        return str(secrets.randbelow(9000) + 1000)  # 🔥 6 digits (important)

    # ---------------------------
    # Send verification email
    # ---------------------------
    @staticmethod
    def send_verification(email: str):

        code = EmailOTPService.generate_code()

        # 🔐 stockage OTP
        OtpService.store_otp("email", email, code)

        subject = "Code de vérification Tikzok"

        # ---------------------------
        # HTML SAFE (iOS / Gmail / Outlook)
        # ---------------------------
        html = f"""
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px;">
  <tr>
    <td align="center">

      <table width="400" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;padding:24px;text-align:center;font-family:Arial,sans-serif;">

        <tr>
          <td style="font-size:20px;font-weight:600;color:#111;">
            Tikzok
          </td>
        </tr>

        <tr>
          <td style="padding-top:12px;font-size:14px;color:#666;">
            Code de vérification
          </td>
        </tr>

        <tr>
          <td style="padding:24px 0;">
            <span style="font-size:34px;font-weight:700;letter-spacing:6px;color:#000;">
              {code}
            </span>
          </td>
        </tr>

        <tr>
          <td style="font-size:12px;color:#999;">
            Ce code expire dans 5 minutes
          </td>
        </tr>

      </table>

    </td>
  </tr>
</table>
"""

        # ---------------------------
        # TEXT (IMPORTANT iOS auto-fill)
        # ---------------------------
        text = f"""yeslek

Votre code de vérification est : {code}

Ce code expire dans 5 minutes.
"""

        EmailService.send_email(
            to_email=email,
            subject=subject,
            html=html,
            text=text
        )

        # ⚠️ uniquement debug
        return code