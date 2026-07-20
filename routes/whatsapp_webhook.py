# ---------------------------
# WhatsApp Webhook Routes
# ---------------------------

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator
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


# ---------------------------
# Blueprint
# ---------------------------

whatsapp_webhook_bp = Blueprint(
    "whatsapp_webhook",
    __name__,
)


# ---------------------------
# Constants
# ---------------------------

WHATSAPP_WEBHOOK_OBJECT = "whatsapp_business_account"
WHATSAPP_MESSAGES_FIELD = "messages"

SUPPORTED_MESSAGE_STATUSES = {
    "sent",
    "delivered",
    "read",
    "failed",
}


# ---------------------------
# Safe logging helpers
# ---------------------------

def _safe_suffix(
    value: Any,
    *,
    length: int = 8,
) -> str:
    """
    Retourne uniquement la fin d'un identifiant afin d'éviter
    d'exposer des données complètes dans les logs.
    """

    clean_value = str(
        value or ""
    ).strip()

    if not clean_value:
        return "unknown"

    return clean_value[-length:]


# ---------------------------
# Configuration helpers
# ---------------------------

def _get_verify_token() -> str:
    return str(
        WHATSAPP_VERIFY_TOKEN or ""
    ).strip()


def _get_meta_app_secret() -> str:
    return str(
        META_APP_SECRET or ""
    ).strip()


# ---------------------------
# Signature validation
# ---------------------------

def _is_valid_meta_signature(
    raw_body: bytes,
    received_signature: str,
) -> bool:
    """
    Vérifie l'en-tête X-Hub-Signature-256 envoyé par Meta.
    """

    app_secret = _get_meta_app_secret()

    clean_signature = str(
        received_signature or ""
    ).strip()

    if not app_secret or not clean_signature:
        return False

    if not clean_signature.startswith("sha256="):
        return False

    expected_digest = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    expected_signature = (
        f"sha256={expected_digest}"
    )

    return hmac.compare_digest(
        expected_signature,
        clean_signature,
    )


# ---------------------------
# Payload iteration
# ---------------------------

def _iter_message_values(
    payload: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    """
    Parcourt les changements WhatsApp portant sur le champ messages.
    """

    entries = payload.get(
        "entry",
        [],
    )

    if not isinstance(entries, list):
        return

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        changes = entry.get(
            "changes",
            [],
        )

        if not isinstance(changes, list):
            continue

        for change in changes:
            if not isinstance(change, dict):
                continue

            field_name = str(
                change.get("field")
                or ""
            ).strip()

            if field_name != WHATSAPP_MESSAGES_FIELD:
                continue

            value = change.get(
                "value",
            )

            if isinstance(value, dict):
                yield value


# ---------------------------
# Status processing
# ---------------------------

def _process_message_statuses(
    value: dict[str, Any],
) -> None:
    """
    Traite les statuts sent, delivered, read et failed.

    La persistance PostgreSQL peut ensuite être appelée ici
    via un service ou un worker Celery.
    """

    statuses = value.get(
        "statuses",
        [],
    )

    if not isinstance(statuses, list):
        return

    for status_payload in statuses:
        if not isinstance(
            status_payload,
            dict,
        ):
            continue

        message_id = str(
            status_payload.get("id")
            or ""
        ).strip()

        message_status = str(
            status_payload.get("status")
            or ""
        ).strip().lower()

        recipient_id = str(
            status_payload.get("recipient_id")
            or ""
        ).strip()

        timestamp = str(
            status_payload.get("timestamp")
            or ""
        ).strip()

        if (
            not message_id
            or message_status
            not in SUPPORTED_MESSAGE_STATUSES
        ):
            continue

        current_app.logger.info(
            (
                "WhatsApp message status received: "
                "status=%s message_suffix=%s "
                "recipient_suffix=%s timestamp=%s"
            ),
            message_status,
            _safe_suffix(
                message_id,
                length=12,
            ),
            _safe_suffix(
                recipient_id,
                length=4,
            ),
            timestamp or "unknown",
        )

        if message_status == "failed":
            errors = status_payload.get(
                "errors",
                [],
            )

            error_code = "unknown"

            if (
                isinstance(errors, list)
                and errors
                and isinstance(errors[0], dict)
            ):
                error_code = str(
                    errors[0].get("code")
                    or "unknown"
                )

            current_app.logger.warning(
                (
                    "WhatsApp message delivery failed: "
                    "message_suffix=%s error_code=%s"
                ),
                _safe_suffix(
                    message_id,
                    length=12,
                ),
                error_code,
            )

        # Exemple d'intégration future :
        #
        # whatsapp_message_service.update_status(
        #     message_id=message_id,
        #     status=message_status,
        #     recipient_id=recipient_id,
        #     timestamp=timestamp,
        # )
        #
        # Cette opération devra être idempotente sur :
        # message_id + message_status.


# ---------------------------
# Incoming message processing
# ---------------------------

def _process_incoming_messages(
    value: dict[str, Any],
) -> None:
    """
    Traite les messages envoyés par les clients au numéro Yeslek.

    Le contenu complet du message n'est jamais écrit dans les logs.
    """

    messages = value.get(
        "messages",
        [],
    )

    if not isinstance(messages, list):
        return

    metadata = value.get(
        "metadata",
        {},
    )

    phone_number_id = ""

    if isinstance(metadata, dict):
        phone_number_id = str(
            metadata.get("phone_number_id")
            or ""
        ).strip()

    for message_payload in messages:
        if not isinstance(
            message_payload,
            dict,
        ):
            continue

        message_id = str(
            message_payload.get("id")
            or ""
        ).strip()

        sender = str(
            message_payload.get("from")
            or ""
        ).strip()

        message_type = str(
            message_payload.get("type")
            or "unknown"
        ).strip().lower()

        timestamp = str(
            message_payload.get("timestamp")
            or ""
        ).strip()

        if not message_id:
            continue

        current_app.logger.info(
            (
                "WhatsApp incoming message received: "
                "type=%s message_suffix=%s "
                "sender_suffix=%s phone_id_suffix=%s "
                "timestamp=%s"
            ),
            message_type,
            _safe_suffix(
                message_id,
                length=12,
            ),
            _safe_suffix(
                sender,
                length=4,
            ),
            _safe_suffix(
                phone_number_id,
                length=6,
            ),
            timestamp or "unknown",
        )

        # Ne jamais journaliser directement :
        #
        # message_payload["text"]["body"]
        #
        # Pour le flux OTP Yeslek, aucune réponse automatique
        # aux messages entrants n'est nécessaire actuellement.
        #
        # Une future persistance devra être idempotente sur message_id.


# ---------------------------
# Webhook verification GET
# ---------------------------

@whatsapp_webhook_bp.get(
    "/webhooks/whatsapp"
)
def verify_whatsapp_webhook() -> Response:
    """
    Valide l'URL de rappel lors de la configuration Meta.
    """

    mode = str(
        request.args.get("hub.mode")
        or request.args.get("hub_mode")
        or ""
    ).strip()

    received_token = str(
        request.args.get("hub.verify_token")
        or request.args.get("hub_verify_token")
        or ""
    ).strip()

    challenge = str(
        request.args.get("hub.challenge")
        or request.args.get("hub_challenge")
        or ""
    ).strip()

    expected_token = _get_verify_token()

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
        and received_token
        and challenge
        and hmac.compare_digest(
            received_token,
            expected_token,
        )
    ):
        current_app.logger.info(
            "WhatsApp webhook verification succeeded"
        )

        return Response(
            challenge,
            status=200,
            mimetype="text/plain",
        )

    current_app.logger.warning(
        (
            "WhatsApp webhook verification refused: "
            "mode=%s token_present=%s challenge_present=%s"
        ),
        mode or "missing",
        bool(received_token),
        bool(challenge),
    )

    return Response(
        "Forbidden",
        status=403,
        mimetype="text/plain",
    )


# ---------------------------
# Webhook events POST
# ---------------------------

@whatsapp_webhook_bp.post(
    "/webhooks/whatsapp"
)
def receive_whatsapp_webhook() -> Response:
    """
    Reçoit les messages entrants et les changements de statut.

    La requête est validée avec X-Hub-Signature-256 avant
    toute lecture ou utilisation du contenu.
    """

    app_secret = _get_meta_app_secret()

    if not app_secret:
        current_app.logger.error(
            "META_APP_SECRET is not configured"
        )

        return Response(
            "Configuration error",
            status=500,
            mimetype="text/plain",
        )

    raw_body = request.get_data(
        cache=True,
        as_text=False,
    )

    received_signature = request.headers.get(
        "X-Hub-Signature-256",
        "",
    )

    if not _is_valid_meta_signature(
        raw_body,
        received_signature,
    ):
        current_app.logger.warning(
            (
                "WhatsApp webhook rejected: "
                "invalid Meta signature"
            )
        )

        return Response(
            "Unauthorized",
            status=401,
            mimetype="text/plain",
        )

    payload = request.get_json(
        silent=True,
    )

    if not isinstance(payload, dict):
        current_app.logger.warning(
            "WhatsApp webhook rejected: invalid JSON"
        )

        return Response(
            "Invalid payload",
            status=400,
            mimetype="text/plain",
        )

    object_type = str(
        payload.get("object")
        or ""
    ).strip()

    if object_type != WHATSAPP_WEBHOOK_OBJECT:
        current_app.logger.info(
            (
                "WhatsApp webhook ignored: "
                "object=%s"
            ),
            object_type or "missing",
        )

        return Response(
            "IGNORED",
            status=200,
            mimetype="text/plain",
        )

    try:
        for value in _iter_message_values(
            payload
        ):
            _process_message_statuses(
                value
            )

            _process_incoming_messages(
                value
            )

    except Exception:
        current_app.logger.exception(
            (
                "Unexpected error while processing "
                "WhatsApp webhook"
            )
        )

        # Une erreur temporaire renvoie 500 afin que Meta
        # puisse retenter la livraison de l'événement.
        return Response(
            "Processing error",
            status=500,
            mimetype="text/plain",
        )

    return Response(
        "EVENT_RECEIVED",
        status=200,
        mimetype="text/plain",
    )