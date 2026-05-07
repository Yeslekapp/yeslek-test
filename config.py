# ---------------------------
# config.py (LIVE ONLY)
# ---------------------------

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ---------------------------
# FORCE LIVE
# ---------------------------

ENV = "production"
IS_PROD = True

# ---------------------------
# Flask (FINAL PRODUCTION SAFE)
# ---------------------------

SECRET_KEY = os.getenv("SECRET_KEY")

SESSION_COOKIE_HTTPONLY = True
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 365  # 1 an

# ---------------------------
# Cookies (FIX Google OAuth)
# ---------------------------

if IS_PROD:
    # ✅ Production (HTTPS obligatoire)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"
else:
    # ✅ Localhost / dev
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"

# ---------------------------
# Database
# ---------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------
# Reloadly API (SAFE MODE)
# ---------------------------

RELOADLY_CLIENT_ID = os.getenv("RELOADLY_CLIENT_ID", "")
RELOADLY_CLIENT_SECRET = os.getenv("RELOADLY_CLIENT_SECRET", "")

# ⚡ dynamique (safe)
RELOADLY_ENV = "LIVE" if IS_PROD else "SANDBOX"
RELOADLY_BASE_URL = "https://topups.reloadly.com"
RELOADLY_AUTH_URL = "https://auth.reloadly.com/oauth/token"

# ---------------------------
# Telnyx SMS OTP
# ---------------------------

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "")
TELNYX_SMS_FROM = os.getenv("TELNYX_SMS_FROM", "")

# ---------------------------
# Brevo (Email)
# ---------------------------

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "Yeslek")

# ---------------------------
# Stripe
# ---------------------------

STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# ⚡ dynamique (safe)
STRIPE_MODE = "live" if IS_PROD else "test"

# ---------------------------
# Payment settings
# ---------------------------

CURRENCY = os.getenv("CURRENCY", "eur")

# ---------------------------
# Admin
# ---------------------------

ADMIN_EMAILS_ENV = {
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

ADMIN_EMAILS_STATIC = {
    "admin@yeslek.com",
    "safarigulahmad616@gmail.com",
    "admin@email.com"
}

ADMIN_EMAILS = ADMIN_EMAILS_ENV.union(ADMIN_EMAILS_STATIC)

SUPER_ADMIN_EMAIL = "admin@yeslek.com"

# ---------------------------
# App
# ---------------------------

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ---------------------------
# Security
# ---------------------------

MAX_CONTENT_LENGTH = 2 * 1024 * 1024

# ---------------------------
# Debug (SAFE)
# ---------------------------

if not IS_PROD:
    print("[RELOADLY]", RELOADLY_BASE_URL)
    print("[STRIPE MODE]", STRIPE_MODE)
# ---------------------------
# Google OAuth
# ---------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "https://yeslek.com/auth/google/callback"
)

# ---------------------------
# FACEBOOK
# ---------------------------
FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
FACEBOOK_REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")