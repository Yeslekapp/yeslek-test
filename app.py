# ---------------------------
# yeslek - Application Entry
# ---------------------------

import os
import json
from copy import deepcopy
from datetime import datetime

from flask import Flask, session, request, g, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

# Optional dotenv (local dev only)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import config
from flask import send_from_directory
from routes.recharge import recharge_bp
from routes.payment import payment_bp
from routes.auth import auth_bp
from routes.i18n import bp as i18n_bp
from routes.account import account_bp
from routes.history import history_bp
from routes.admin import admin_bp
from routes.reloadly import reloadly_bp
from routes.seo import seo_bp
from routes.legal import legal_bp
# ---------------------------
# Create tables (TEMP)
# ---------------------------
from db.database import Base, engine
Base.metadata.create_all(bind=engine)
# ---------------------------
# Create payment tables (TEMP)
# ---------------------------
from services.core.db_service import db_cursor

def _ensure_payment_tables() -> None:

    with db_cursor(commit=True) as cur:

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stripe_customers (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                email TEXT,
                stripe_customer_id TEXT NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_cards (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                stripe_customer_id TEXT NOT NULL,
                payment_method_id TEXT NOT NULL UNIQUE,
                brand TEXT NOT NULL DEFAULT 'card',
                last4 TEXT NOT NULL,
                exp_month INTEGER NOT NULL,
                exp_year INTEGER NOT NULL,
                expiry TEXT NOT NULL,
                fingerprint TEXT,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                deleted_at TIMESTAMPTZ
            );
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_saved_cards_user_id
            ON saved_cards(user_id);
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_saved_cards_user_active
            ON saved_cards(user_id, deleted_at);
            """
        )

        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_cards_user_fingerprint_active
            ON saved_cards(user_id, fingerprint)
            WHERE fingerprint IS NOT NULL AND deleted_at IS NULL;
            """
        )

_ensure_payment_tables()
# ---------------------------
# Helpers
# ---------------------------
def _deep_merge_dict(base: dict, extra: dict) -> dict:
    merged = deepcopy(base)

    for key, value in (extra or {}).items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value

    return merged


# ---------------------------
# App Factory
# ---------------------------
def create_app() -> Flask:

    app = Flask(__name__)

    from datetime import timedelta

    # ---------------------------
    # Session lifetime
    # ---------------------------
    app.permanent_session_lifetime = timedelta(days=365 * 5)

    # ---------------------------
    # Proxy (IMPORTANT HTTPS / Cloud)
    # ---------------------------
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # ---------------------------
    # Security Config (FINAL FIX)
    # ---------------------------
    app.secret_key = config.SECRET_KEY or os.getenv("FLASK_SECRET_KEY")

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY must be set")

    app.config["SESSION_COOKIE_NAME"] = "yeslek_session"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365 * 5)

    # ---------------------------
    # Cookies (FINAL GOOGLE FIX)
    # ---------------------------

    app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE

     # garde login Google après reload / fermeture
    app.config["SESSION_REFRESH_EACH_REQUEST"] = False

    # ---------------------------
    # Global config (TOUJOURS ACTIF)
    # ---------------------------
    app.config["PREFERRED_URL_SCHEME"] = "https"
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # ---------------------------
    # Inject current time
    # ---------------------------
    @app.context_processor
    def inject_now():
        return dict(now=datetime.now)

    # ---------------------------
    # Stripe key
    # ---------------------------
    @app.context_processor
    def inject_stripe_key():
        return dict(STRIPE_PUBLIC_KEY=config.STRIPE_PUBLIC_KEY)

    @app.route("/sitemap.xml")
    def sitemap():
        return send_from_directory("static", "sitemap.xml")

    # ---------------------------
    # App meta
    # ---------------------------
    @app.context_processor
    def inject_app_meta():
        user_email = (session.get("user_email") or "").strip().lower()
        is_admin_user = bool(session.get("is_admin")) or user_email in config.ADMIN_EMAILS

        return dict(
            APP_VERSION=config.APP_VERSION,
            is_admin_user=is_admin_user,
        )

    # ---------------------------
    # I18n loader
    # ---------------------------
    def _load_json_file(path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_l10n(lang: str) -> dict:

        allowed = {"fr", "en", "ar", "fa", "ps", "uz", "tr", "de"}

        if lang not in allowed:
            lang = "en"

        base_dir = os.path.join(os.path.dirname(__file__), "l10n")

        base_path = os.path.join(base_dir, f"{lang}.json")
        admin_path = os.path.join(base_dir, f"admin.{lang}.json")

        base_data = _load_json_file(base_path)
        admin_data = _load_json_file(admin_path)

        return _deep_merge_dict(base_data, admin_data)

    # ---------------------------
    # Set lang (FINAL PRODUCTION)
    # ---------------------------
    @app.before_request
    def _set_lang():

        allowed = {"fr", "en", "ar", "fa", "ps", "uz", "tr", "de"}

        lang = session.get("lang")

        if not lang:
            lang = request.cookies.get("lang")

        if not lang:
            lang = request.args.get("lang")

        if not lang:
            accept = request.headers.get("Accept-Language", "")
            lang = None

            if accept:
                for l in accept.split(","):
                    code = l.split(";")[0].strip()
                    short = code.split("-")[0]

                    if short in allowed:
                        lang = short
                        break

        if not lang:
            lang = "en"

        if lang not in allowed:
            lang = "en"

        session["lang"] = lang
        g.lang = lang
        g.l10n = _load_l10n(lang)

        user_email = (session.get("user_email") or "").strip().lower()
        session["is_admin"] = user_email in config.ADMIN_EMAILS


    # ---------------------------
    # Security headers
    # ---------------------------
    @app.after_request
    def _security_headers(response):

        response.headers.setdefault(
            "X-Content-Type-Options",
            "nosniff"
        )

        response.headers.setdefault(
            "X-Frame-Options",
            "SAMEORIGIN"
        )

        response.headers.setdefault(
            "Referrer-Policy",
            "strict-origin-when-cross-origin"
        )

        if request.path.startswith("/payment"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response
    # ---------------------------
    # Translation helper
    # ---------------------------
    def t(key: str, params: dict | None = None, default: str = "") -> str:

        cur = g.get("l10n", {})

        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default or key
            cur = cur[part]

        if not isinstance(cur, str):
            return default or key

        if params:
            for k, v in params.items():
                cur = cur.replace(f"{{{k}}}", str(v))

        return cur

    app.jinja_env.globals["t"] = t

    # ---------------------------
    # Blueprints
    # ---------------------------
    app.register_blueprint(recharge_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(i18n_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reloadly_bp)
    app.register_blueprint(seo_bp)
    app.register_blueprint(legal_bp)

    return app

# ---------------------------
# App Init
# ---------------------------
app = create_app()

# ---------------------------
# SEO - Robots.txt
# ---------------------------
from flask import Response

@app.route("/robots.txt")
def robots():
    content = []
    content.append("User-agent: *")
    content.append("Allow: /")
    content.append("")
    content.append("Sitemap: " + url_for("sitemap", _external=True))

    return Response("\n".join(content), mimetype="text/plain")

# ---------------------------
# Apple Pay domain verification
# ---------------------------
from flask import send_from_directory

@app.route('/.well-known/apple-developer-merchantid-domain-association')
def apple_pay_verification():
    return send_from_directory(
        'static/.well-known',
        'apple-developer-merchantid-domain-association'
    )

@app.route("/")
def index():
    return redirect(url_for("recharge.enter_number_get"))
# ---------------------------
# Debug: Stripe environment check
# ---------------------------
@app.route("/__debug/stripe")
def debug_stripe_config():

    if not config.IS_TEST:
        return {
            "ok": False,
            "error": "not_available_in_production",
        }, 404

    public_key = config.STRIPE_PUBLIC_KEY or ""
    secret_key = config.STRIPE_SECRET_KEY or ""

    return {
        "ok": True,
        "app_env": config.ENV,
        "app_base_url": config.APP_BASE_URL,
        "stripe_mode": config.STRIPE_MODE,
        "stripe_public_key_type": (
            "test"
            if public_key.startswith("pk_test_")
            else "live"
            if public_key.startswith("pk_live_")
            else "missing"
        ),
        "stripe_secret_key_type": (
            "test"
            if secret_key.startswith("sk_test_")
            else "live"
            if secret_key.startswith("sk_live_")
            else "missing"
        ),
        "stripe_public_key_prefix": public_key[:12],
    }

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        debug=os.getenv("ENV") != "production",
        use_reloader=False  # ✅ FIX CRASH WINDOWS
    )