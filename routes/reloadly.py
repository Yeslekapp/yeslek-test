# ---------------------------
# Feature: Reloadly Webhook (FULL PRODUCTION)
# ---------------------------

from __future__ import annotations

import os
import hmac
import hashlib
import logging
from typing import Any, Dict

from flask import Blueprint, request, jsonify

from services.reloadly.transaction_service import normalize_reloadly_status

reloadly_bp = Blueprint("reloadly", __name__, url_prefix="/reloadly")

logger = logging.getLogger(__name__)

# ---------------------------
# Config
# ---------------------------

SIGNING_SECRET = os.getenv("RELOADLY_WEBHOOK_SECRET", "")

ALLOWED_IPS = {
    "54.84.138.60",
    "54.84.66.109",
}


# ---------------------------
# Helpers
# ---------------------------

def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _verify_signature(payload: str, signature: str, timestamp: str) -> bool:
    if not SIGNING_SECRET:
        logger.warning("⚠️ Missing RELOADLY_WEBHOOK_SECRET")
        return True  # fallback dev

    try:
        data_to_sign = f"{payload}:{timestamp}"

        computed = hmac.new(
            SIGNING_SECRET.encode(),
            data_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed, signature)

    except Exception:
        logger.exception("❌ Signature verification error")
        return False


# ---------------------------
# Webhook Endpoint
# ---------------------------

@reloadly_bp.post("/webhook")
def reloadly_webhook():
    data = request.get_json() or {}
    print("🔥 RELOADLY EVENT:", data)
    # ---------------------------
    # 🔒 IP SECURITY
    # ---------------------------
    client_ip = _get_client_ip()

    if client_ip not in ALLOWED_IPS:
        logger.warning("❌ Unauthorized IP: %s", client_ip)
        return jsonify({"ok": False}), 403

    # ---------------------------
    # 🔒 SIGNATURE SECURITY
    # ---------------------------
    payload = request.data.decode("utf-8")

    signature = request.headers.get("X-Reloadly-Signature", "")
    timestamp = request.headers.get("X-Reloadly-Request-Timestamp", "")

    if not _verify_signature(payload, signature, timestamp):
        logger.warning("❌ Invalid signature")
        return jsonify({"ok": False}), 400

    # ---------------------------
    # Parse event
    # ---------------------------
    data: Dict[str, Any] = request.get_json() or {}

    logger.info("🔥 RELOADLY EVENT: %s", data)

    event_type = data.get("type")

    # ---------------------------
    # Extract fields
    # ---------------------------
    transaction_id = data.get("transactionId")
    reference = data.get("customIdentifier")
    raw_status = data.get("status")

    if not reference:
        logger.warning("⚠️ Missing reference")
        return jsonify({"ok": True}), 200

    status = normalize_reloadly_status(raw_status)

    # ---------------------------
    # Update DB
    # ---------------------------
    try:
        from db.database import SessionLocal
        from db.models.transaction import Transaction

        db = SessionLocal()

        tx = db.query(Transaction).filter(
            Transaction.reference == reference
        ).first()

        if not tx:
            logger.warning("⚠️ Transaction not found: %s", reference)
            return jsonify({"ok": True}), 200

        tx.status = status

        if transaction_id and hasattr(tx, "reloadly_transaction_id"):
            tx.reloadly_transaction_id = transaction_id

        db.commit()

        logger.info("✅ Transaction updated: %s → %s", reference, status)

    except Exception as e:
        logger.exception("❌ DB error: %s", e)
        return jsonify({"ok": False}), 500

    finally:
        db.close()

    # ---------------------------
    # Business logic (optionnel)
    # ---------------------------
    if status == "SUCCESS":
        logger.info("🎉 Recharge SUCCESS")

    elif status in {"FAILED", "REFUNDED"}:
        logger.warning("💥 Recharge FAILED")

    return jsonify({"ok": True}), 200