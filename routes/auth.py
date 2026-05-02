# ---------------------------
# Auth Routes — FINAL CLEAN (OTP + Google FIX)
# ---------------------------

from flask import Blueprint, render_template, request, session, redirect, url_for
import re
import time
import os

# 🔥 FIX GOOGLE LOCAL (HTTP autorisé en dev)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from google_auth_oauthlib.flow import Flow
import requests

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
# GOOGLE CONFIG
# ---------------------------
from config import (
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
    FACEBOOK_APP_ID,
    FACEBOOK_APP_SECRET,
    FACEBOOK_REDIRECT_URI
)

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
# GOOGLE LOGIN
# ============================================================
@auth_bp.route("/google/login")
def google_login():

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid"
        ]
    )

    flow.redirect_uri = GOOGLE_REDIRECT_URI

    auth_url, state = flow.authorization_url(
        prompt="select_account",
        access_type="offline",
        code_challenge=None 
    )

    session["google_oauth_state"] = state

    return redirect(auth_url)

# ============================================================
# GOOGLE callback
# ============================================================
@auth_bp.route("/google/callback")
def google_callback():
    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [GOOGLE_REDIRECT_URI]
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "openid"
            ],
            state=session.get("google_oauth_state")
        )

        flow.redirect_uri = GOOGLE_REDIRECT_URI

        # ---------------------------
        # Sécurité erreur Google
        # ---------------------------
        if "error" in request.args:
            return redirect(url_for("auth.login"))

        # ---------------------------
        # Exchange token
        # ---------------------------
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials

        # ---------------------------
        # Get user info
        # ---------------------------
        res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=5
        )

        if res.status_code != 200:
            return redirect(url_for("auth.login"))

        userinfo = res.json()

        email = userinfo.get("email")
        name = userinfo.get("name")

        if not email:
            return redirect(url_for("auth.login"))

        # ---------------------------
        # USER DB
        # ---------------------------
        user = get_or_create_user(email=email, name=name)

        # ---------------------------
        # SESSION LOGIN
        # ---------------------------
        session["user_id"] = user.id
        session["user_email"] = email
        session["user_name"] = name
        session.permanent = True

        # cleanup
        session.pop("google_oauth_state", None)

        print("SESSION AFTER GOOGLE LOGIN:", dict(session))

        # ---------------------------
        # REDIRECT FINAL
        # ---------------------------
        return redirect(url_for("recharge.enter_number_get"))

    except Exception as e:
        print("GOOGLE CALLBACK ERROR:", str(e))
        return redirect(url_for("auth.login"))
# ============================================================
# LOGIN facebook
# ============================================================
import secrets

@auth_bp.route("/facebook/login")
def facebook_login():

    state = secrets.token_urlsafe(16)

    session["fb_oauth_state"] = state

    fb_auth_url = (
        "https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={FACEBOOK_APP_ID}"
        f"&redirect_uri={FACEBOOK_REDIRECT_URI}"
        "&scope=email,public_profile"
        f"&state={state}"
    )

    return redirect(fb_auth_url)

# ============================================================
#   callbackfacebook
# ============================================================
@auth_bp.route("/facebook/callback")
def facebook_callback():

    code = request.args.get("code")
    state = request.args.get("state")

    if not code or state != session.get("fb_oauth_state"):
        return redirect(url_for("auth.login"))

    try:
        token_url = (
            "https://graph.facebook.com/v18.0/oauth/access_token"
            f"?client_id={FACEBOOK_APP_ID}"
            f"&redirect_uri={FACEBOOK_REDIRECT_URI}"
            f"&client_secret={FACEBOOK_APP_SECRET}"
            f"&code={code}"
        )

        token_res = requests.get(token_url).json()
        access_token = token_res.get("access_token")

        if not access_token:
            return redirect(url_for("auth.login"))

        user_res = requests.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,name,email,picture",
                "access_token": access_token
            }
        ).json()

        email = user_res.get("email")
        name = user_res.get("name")
        avatar = user_res.get("picture", {}).get("data", {}).get("url")
        if not email:
         email = f"{user_res.get('id')}@facebook.com"
         
        if not email:
            return redirect(url_for("auth.login"))

        user = get_or_create_user(email=email, name=name)

        session["user_id"] = user.id
        session["user_email"] = email
        session["user_name"] = name
        session["user_avatar"] = avatar
        session.permanent = True

        session.pop("fb_oauth_state", None)

        print("SESSION AFTER FACEBOOK LOGIN:", dict(session))

        return redirect(url_for("recharge.enter_number_get"))

    except Exception as e:
        print("FACEBOOK ERROR:", e)
        return redirect(url_for("auth.login"))

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

        user = get_or_create_user(email=email_value)

        session["user_id"] = user.id
        session["user_email"] = email_value
        session.permanent = True

        session.pop("pending_email", None)
        session.pop("email_last_sent", None)

        return redirect("/", code=303)

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
        session.permanent = True

        session.pop("pending_phone", None)

        return redirect("/", code=303)

    return render_template(
        "auth/otp.html",
        phone=phone_value,
        masked_phone=_mask_phone(phone_value)
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