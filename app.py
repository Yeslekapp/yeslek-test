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

from routes.recharge import recharge_bp
from routes.payment import payment_bp
from routes.auth import auth_bp
from routes.i18n import bp as i18n_bp
from routes.account import account_bp
from routes.history import history_bp
from routes.admin import admin_bp
from routes.wallet import wallet_bp
# ---------------------------
# Create tables (TEMP)
# ---------------------------
from db.database import Base, engine
Base.metadata.create_all(bind=engine)
# ---------------------------
# Auto migrate: add balance column
# ---------------------------
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN balance FLOAT DEFAULT 0"
        ))
        conn.commit()
    except Exception:
        pass
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
    app.permanent_session_lifetime = timedelta(days=365 * 5)

    # Proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    # ---------------------------
    # Security Config
    # ---------------------------
    app.secret_key = config.SECRET_KEY or os.getenv("FLASK_SECRET_KEY")

    if not app.secret_key:
        raise RuntimeError("SECRET_KEY must be set")

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("ENV") == "production"
    app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME", "https")
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
    # Inject user balance
    # ---------------------------
    @app.before_request
    def inject_user_balance():

        user_id = session.get("user_id")

        if not user_id:
            session["user_balance"] = 0.0
            return

        if "user_balance" in session:
            return

        try:
            from services.user.user_service import UserService
            balance = UserService.get_balance(user_id)
            session["user_balance"] = float(balance or 0.0)
        except Exception:
            session["user_balance"] = 0.0

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
    app.register_blueprint(wallet_bp)

    return app

# ---------------------------
# App Init
# ---------------------------
app = create_app()

# ---------------------------
# SEO - Sitemap XML
# ---------------------------
from flask import Response
from datetime import datetime

@app.route("/sitemap.xml")
def sitemap():

    pages = []

    pages.append(url_for("index", _external=True))
    pages.append(url_for("recharge.enter_number_get", _external=True))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for page in pages:
        xml.append("<url>")
        xml.append(f"<loc>{page}</loc>")
        xml.append(f"<lastmod>{datetime.utcnow().date()}</lastmod>")
        xml.append("<changefreq>daily</changefreq>")
        xml.append("<priority>0.9</priority>")
        xml.append("</url>")

    xml.append("</urlset>")

    return Response("\n".join(xml), mimetype="application/xml")

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

@app.route("/")
def index():
    return redirect(url_for("recharge.enter_number_get"))



if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        debug=os.getenv("ENV") != "production",
        use_reloader=False  # ✅ FIX CRASH WINDOWS
    )