# ---------------------------
# Auth Routes — FINAL CLEAN (OTP + Redis)
# ---------------------------

from flask import Blueprint, render_template, request, session, redirect, url_for
import re
import time

from services.communication.email_otp_service import EmailOTPService
from services.communication.sms_service import SMSService
from services.communication.otp_service import OtpService
from services.auth_service import get_or_create_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ---------------------------
# CONFIG OTP
# ---------------------------
OTP_RESEND_COOLDOWN = 30


# ---------------------------
# Helpers
# ---------------------------
def _valid_email(email: str):
    if not email:
        return False

    email = email.strip().lower()
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"

    return re.match(pattern, email) is not None


def _mask_phone(phone: str) -> str:
    if not phone:
        return ""
    p = phone.strip()
    if len(p) <= 4:
        return "****"
    return f"{p[:3]} **** {p[-2:]}"


# ============================================================
# LOGIN EMAIL
# ============================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        name = (request.form.get("name") or "").strip()
        email_value = (request.form.get("email") or "").strip().lower()

        if not _valid_email(email_value):
            return render_template("auth/email_login.html", error=True)

        if name:
            session["user_name"] = name

        # cooldown anti spam
        last_sent = session.get("email_last_sent")
        if last_sent and time.time() - last_sent < OTP_RESEND_COOLDOWN:
            return render_template("auth/email_login.html", error=True)

        try:
         lang = session.get("lang", "fr")

         EmailOTPService.send_verification(email_value, lang)

        except Exception as e:
            print("EMAIL ERROR:", e)
            return render_template("auth/email_login.html", error=True)

        session["pending_email"] = email_value
        session["email_last_sent"] = time.time()

        return redirect(url_for("auth.email_code"))

    return render_template("auth/email_login.html")


# ============================================================
# EMAIL OTP VERIFY
# ============================================================
@auth_bp.route("/email-code", methods=["GET", "POST"])
def email_code():

    email_value = session.get("pending_email")

    if not email_value:
        return redirect(url_for("auth.login"))

    if request.method == "POST":

        entered_code = (request.form.get("code") or "").strip()

        valid = OtpService.verify_otp("email", email_value, entered_code)

        if not valid:
            return render_template(
                "auth/email_code.html",
                email=email_value,
                error=True
            )

        # ✅ USER DB
        user = get_or_create_user(email=email_value)

        session["user_id"] = user.id
        session["user_email"] = email_value
        session.permanent = True  # 🔥 AJOUTE ÇA
        session.pop("pending_email", None)
        session.pop("email_last_sent", None)

        next_url = request.args.get("next")
        return redirect(next_url or "/", code=303)

    return render_template("auth/email_code.html", email=email_value)


# ============================================================
# PHONE LOGIN
# ============================================================
@auth_bp.route("/phone", methods=["GET", "POST"])
def phone():

    if request.method == "POST":

        name = (request.form.get("name") or "").strip()
        local_number = request.form.get("phone")
        country_code = request.form.get("country_code")

        if not local_number:
            return render_template("auth/phone_login.html", error=True)

        phone_number = f"{country_code}{local_number}".replace(" ", "")

        if name:
            session["user_name"] = name

        try:
            code = OtpService.generate_code()

            OtpService.store_otp("sms", phone_number, code)

            SMSService.send_sms(
                phone_number,
                f"Your Tikzok verification code is {code}"
            )

        except Exception as e:
            print("TELNYX ERROR:", e)
            return render_template("auth/phone_login.html", error=True)

        session["pending_phone"] = phone_number

        return redirect(url_for("auth.otp"))

    return render_template("auth/phone_login.html")


# ============================================================
# PHONE OTP VERIFY
# ============================================================
@auth_bp.route("/otp", methods=["GET", "POST"])
def otp():

    phone_value = session.get("pending_phone")

    if not phone_value:
        return redirect(url_for("auth.phone"))

    if request.method == "POST":

        entered_code = (request.form.get("code") or "").strip()

        valid = OtpService.verify_otp("sms", phone_value, entered_code)

        if not valid:
            return render_template(
                "auth/otp.html",
                phone=phone_value,
                error=True
            )

        user = get_or_create_user(phone=phone_value)

        session["user_id"] = user.id
        session["user_phone"] = phone_value
        session.permanent = True  # 🔥 AJOUTE ÇA
        session.pop("pending_phone", None)

        next_url = request.args.get("next")
    return redirect(next_url or "/", code=303) 

    masked_phone = _mask_phone(phone_value)

    return render_template(
        "auth/otp.html",
        phone=phone_value,
        masked_phone=masked_phone
    )


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ============================================================
# LOGOUT CONFIRM
# ============================================================
@auth_bp.route("/logout-confirm")
def logout_confirm():

    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    return render_template("auth/logout_confirm.html")