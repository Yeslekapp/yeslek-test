# ---------------------------
# WhatsApp Webhook Routes
# ---------------------------

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from flask import (
    Blueprint,
    Response,
    current_app,
    request,
)

from config import (
    META_APP_SECRET,
    WHATSAPP_VERIFY_TOKEN,
)


whatsapp_webhook_bp = Blueprint(
    "whatsapp_webhook",
    __name__,
)


# ---------------------------
# Webhook signature validation
# ---------------------------

def _is_valid_meta_signature(
    raw_body: bytes,
    received_signature: str,
) -> bool:
    """
    Vérifie que la requête POST provient réellement de Meta.
    """

    app_secret = str(
        META_APP_SECRET or ""
    ).strip()

    signature = str(
        received_signature or ""
    ).strip()

    if not app_secret or not signature:
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        expected_signature,
        signature,
    )


# ---------------------------
# Meta webhook verification
# ---------------------------

@whatsapp_webhook_bp.get("/webhooks/whatsapp")
def verify_whatsapp_webhook() -> Response:
    """
    Répond à la demande de validation initiale envoyée par Meta.
    """

    mode = str(
        request.args.get("hub.mode")
        or ""
    ).strip()

    received_token = str(
        request.args.get("hub.verify_token")
        or ""
    ).strip()

    challenge = str(
        request.args.get("hub.challenge")
        or ""
    ).strip()

    expected_token = str(
        WHATSAPP_VERIFY_TOKEN or ""
    ).strip()

    if not expected_token:
        current_app.logger.error(
            "WHATSAPP_VERIFY_TOKEN is not configured"
        )

        return Response(
            "Configuration error",
            status=500,
            mimetype="text/plain",
        )

    if (
        mode == "subscribe"
        and challenge
        and received_token
        and hmac.compare_digest(
            received_token,
            expected_token,
        )
    ):
        current_app.logger.info(
            "WhatsApp webhook verification succeeded"
        )

        # Meta attend uniquement le challenge, sans JSON.
        return Response(
            challenge,
            status=200,
            mimetype="text/plain",
        )

    current_app.logger.warning(
        "WhatsApp webhook verification refused"
    )

    return Response(
        "Forbidden",
        status=403,
        mimetype="text/plain",
    )


# ---------------------------
# Receive WhatsApp events
# ---------------------------

@whatsapp_webhook_bp.post("/webhooks/whatsapp")
def receive_whatsapp_webhook() -> Response:
    """
    Reçoit les statuts et événements WhatsApp.

    Le traitement Celery et la persistance seront ajoutés séparément.
    """

    raw_body = request.get_data(
        cache=True,
        as_text=False,
    )

    received_signature = request.headers.get(
        "X-Hub-Signature-256",
        "",
    )

    if not META_APP_SECRET:
        current_app.logger.error(
            "META_APP_SECRET is not configured"
        )

        return Response(
            "Configuration error",
            status=500,
            mimetype="text/plain",
        )

    if not _is_valid_meta_signature(
        raw_body,
        received_signature,
    ):
        current_app.logger.warning(
            "Invalid WhatsApp webhook signature"
        )

        return Response(
            "Unauthorized",
            status=401,
            mimetype="text/plain",
        )

    payload: Any = request.get_json(
        silent=True,
    )

    if not isinstance(payload, dict):
        return Response(
            "Invalid payload",
            status=400,
            mimetype="text/plain",
        )

    if payload.get("object") != "whatsapp_business_account":
        return Response(
            "Ignored",
            status=200,
            mimetype="text/plain",
        )

    # Ne pas journaliser le payload complet :
    # il peut contenir des numéros et des messages clients.
    current_app.logger.info(
        "WhatsApp webhook event received"
    )

    return Response(
        "EVENT_RECEIVED",
        status=200,
        mimetype="text/plain",
    )