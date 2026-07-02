# ---------------------------
# config.py (TEST + PRODUCTION SAFE)
# ---------------------------

from __future__ import annotations

import os


# ---------------------------
# Load .env local
# ---------------------------

try:
    from dotenv import load_dotenv

    load_dotenv()

except Exception:
    pass


# ---------------------------
# Environment
# ---------------------------

ENV = os.getenv(
    "APP_ENV",
    "production",
).strip().lower()

IS_PROD = ENV in {
    "production",
    "prod",
    "live",
}

IS_TEST = ENV in {
    "test",
    "testing",
    "sandbox",
    "staging",
}

IS_LOCAL = ENV in {
    "local",
    "dev",
    "development",
}


# ---------------------------
# App base URL
# ---------------------------

APP_BASE_URL = os.getenv(
    "APP_BASE_URL",
    "https://yeslek.com" if IS_PROD else "https://test.yeslek.com",
).rstrip("/")


# ---------------------------
# Flask
# ---------------------------

SECRET_KEY = (
    os.getenv("SECRET_KEY")
    or os.getenv("FLASK_SECRET_KEY")
    or ""
)

FLASK_SECRET_KEY = SECRET_KEY

SESSION_COOKIE_HTTPONLY = True
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 365


# ---------------------------
# Cookies
# ---------------------------

if IS_LOCAL:
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"

else:
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "None"


# ---------------------------
# Database
# ---------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
)


# ---------------------------
# Reloadly API
# ---------------------------

RELOADLY_CLIENT_ID = os.getenv(
    "RELOADLY_CLIENT_ID",
    "",
)

RELOADLY_CLIENT_SECRET = os.getenv(
    "RELOADLY_CLIENT_SECRET",
    "",
)

RELOADLY_ENV = os.getenv(
    "RELOADLY_ENV",
    "LIVE" if IS_PROD else "SANDBOX",
).strip().upper()

RELOADLY_AUTH_URL = os.getenv(
    "RELOADLY_AUTH_URL",
    "https://auth.reloadly.com/oauth/token",
)

if RELOADLY_ENV in {
    "SANDBOX",
    "TEST",
    "TESTING",
}:
    RELOADLY_BASE_URL = os.getenv(
        "RELOADLY_BASE_URL",
        "https://topups-sandbox.reloadly.com",
    )

    RELOADLY_AUDIENCE = os.getenv(
        "RELOADLY_AUDIENCE",
        "https://topups-sandbox.reloadly.com",
    )

else:
    RELOADLY_BASE_URL = os.getenv(
        "RELOADLY_BASE_URL",
        "https://topups.reloadly.com",
    )

    RELOADLY_AUDIENCE = os.getenv(
        "RELOADLY_AUDIENCE",
        "https://topups.reloadly.com",
    )


# ---------------------------
# Stripe
# ---------------------------

STRIPE_PUBLIC_KEY = os.getenv(
    "STRIPE_PUBLIC_KEY",
    "",
)

STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    "",
)

STRIPE_WEBHOOK_SECRET = os.getenv(
    "STRIPE_WEBHOOK_SECRET",
    "",
)

STRIPE_MODE = os.getenv(
    "STRIPE_MODE",
    "live" if IS_PROD else "test",
).strip().lower()


# ---------------------------
# Telnyx SMS OTP
# ---------------------------

TELNYX_API_KEY = os.getenv(
    "TELNYX_API_KEY",
    "",
)

TELNYX_SMS_FROM = os.getenv(
    "TELNYX_SMS_FROM",
    "",
)


# ---------------------------
# Brevo Email
# ---------------------------

BREVO_API_KEY = os.getenv(
    "BREVO_API_KEY",
    "",
)

BREVO_FROM_EMAIL = os.getenv(
    "BREVO_FROM_EMAIL",
    "",
)

BREVO_FROM_NAME = os.getenv(
    "BREVO_FROM_NAME",
    "Yeslek",
)


# ---------------------------
# Cloudflare Turnstile
# ---------------------------

TURNSTILE_SITE_KEY = os.getenv(
    "TURNSTILE_SITE_KEY",
    "",
)

TURNSTILE_SECRET_KEY = os.getenv(
    "TURNSTILE_SECRET_KEY",
    "",
)


# ---------------------------
# Payment settings
# ---------------------------

CURRENCY = os.getenv(
    "CURRENCY",
    "eur",
).lower()


# ---------------------------
# Google OAuth
# ---------------------------

GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "",
)

GOOGLE_CLIENT_SECRET = os.getenv(
    "GOOGLE_CLIENT_SECRET",
    "",
)

GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI",
    f"{APP_BASE_URL}/auth/google/callback",
)


# ---------------------------
# Facebook OAuth
# ---------------------------

FACEBOOK_APP_ID = os.getenv(
    "FACEBOOK_APP_ID",
    "",
)

FACEBOOK_APP_SECRET = os.getenv(
    "FACEBOOK_APP_SECRET",
    "",
)

FACEBOOK_REDIRECT_URI = os.getenv(
    "FACEBOOK_REDIRECT_URI",
    f"{APP_BASE_URL}/auth/facebook/callback",
)


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
    "admin@email.com",
}

ADMIN_EMAILS = ADMIN_EMAILS_ENV.union(
    ADMIN_EMAILS_STATIC
)

SUPER_ADMIN_EMAIL = os.getenv(
    "SUPER_ADMIN_EMAIL",
    "admin@yeslek.com",
).strip().lower()


# ---------------------------
# App version
# ---------------------------

APP_VERSION = os.getenv(
    "APP_VERSION",
    "1.0.0",
)


# ---------------------------
# Security
# ---------------------------

MAX_CONTENT_LENGTH = int(
    os.getenv(
        "MAX_CONTENT_LENGTH",
        str(2 * 1024 * 1024),
    )
)


# ---------------------------
# Safe debug logs
# ---------------------------

if not IS_PROD:
    print("[APP ENV]", ENV)
    print("[APP BASE URL]", APP_BASE_URL)
    print("[RELOADLY ENV]", RELOADLY_ENV)
    print("[RELOADLY BASE URL]", RELOADLY_BASE_URL)
    print("[STRIPE MODE]", STRIPE_MODE)