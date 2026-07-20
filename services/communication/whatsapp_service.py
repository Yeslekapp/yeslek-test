# ---------------------------
# WhatsApp Cloud API Service
# ---------------------------

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import requests

from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_GRAPH_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TEMPLATE_OTP_LANGUAGE,
    WHATSAPP_TEMPLATE_OTP_NAME,
)


# ---------------------------
# Exceptions
# ---------------------------

class WhatsAppServiceError(RuntimeError):
    """
    Erreur contrôlée lors d'un appel à WhatsApp Cloud API.
    """


# ---------------------------
# Results
# ---------------------------

@dataclass(frozen=True)
class WhatsAppMessageResult:
    message_id: str
    recipient_wa_id: str | None = None


# ---------------------------
# WhatsApp Service
# ---------------------------

class WhatsAppService:

    CONNECT_TIMEOUT_SECONDS = 5
    READ_TIMEOUT_SECONDS = 15

    @staticmethod
    def _validate_configuration() -> None:
        required_values = {
            "WHATSAPP_GRAPH_API_VERSION": WHATSAPP_GRAPH_API_VERSION,
            "WHATSAPP_ACCESS_TOKEN": WHATSAPP_ACCESS_TOKEN,
            "WHATSAPP_PHONE_NUMBER_ID": WHATSAPP_PHONE_NUMBER_ID,
            "WHATSAPP_TEMPLATE_OTP_NAME": WHATSAPP_TEMPLATE_OTP_NAME,
            "WHATSAPP_TEMPLATE_OTP_LANGUAGE": (
                WHATSAPP_TEMPLATE_OTP_LANGUAGE
            ),
        }

        missing = [
            name
            for name, value in required_values.items()
            if not value
        ]

        if missing:
            raise WhatsAppServiceError(
                "Configuration WhatsApp absente : "
                + ", ".join(missing)
            )

        if not re.fullmatch(
            r"v\d+\.\d+",
            WHATSAPP_GRAPH_API_VERSION,
        ):
            raise WhatsAppServiceError(
                "WHATSAPP_GRAPH_API_VERSION est invalide"
            )

        if not WHATSAPP_PHONE_NUMBER_ID.isdigit():
            raise WhatsAppServiceError(
                "WHATSAPP_PHONE_NUMBER_ID est invalide"
            )

    @staticmethod
    def _normalize_recipient(to_number: str) -> str:
        """
        Transforme +33612345678 en 33612345678 pour Meta.
        """

        clean_number = re.sub(
            r"[^\d+]",
            "",
            str(to_number or "").strip(),
        )

        if not re.fullmatch(
            r"\+[1-9]\d{7,14}",
            clean_number,
        ):
            raise WhatsAppServiceError(
                "Le numéro WhatsApp doit être au format E.164"
            )

        return clean_number[1:]

    @staticmethod
    def _extract_error_message(data: dict[str, Any]) -> str:
        error = data.get("error")

        if not isinstance(error, dict):
            return "WhatsApp Cloud API a refusé le message"

        message = str(
            error.get("message")
            or "WhatsApp Cloud API a refusé le message"
        )

        code = error.get("code")

        if code is not None:
            return f"{message} (code Meta : {code})"

        return message

    @classmethod
    def send_otp(
        cls,
        to_number: str,
        code: str,
    ) -> WhatsAppMessageResult:
        """
        Envoie un OTP avec le modèle Meta yeslek_otp.
        """

        cls._validate_configuration()

        clean_code = str(code or "").strip()

        if not re.fullmatch(r"\d{6}", clean_code):
            raise WhatsAppServiceError(
                "Le code OTP doit contenir exactement 6 chiffres"
            )

        recipient = cls._normalize_recipient(to_number)

        url = (
            "https://graph.facebook.com/"
            f"{WHATSAPP_GRAPH_API_VERSION}/"
            f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
        )

        headers = {
            "Authorization": (
                f"Bearer {WHATSAPP_ACCESS_TOKEN}"
            ),
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "template",
            "template": {
                "name": WHATSAPP_TEMPLATE_OTP_NAME,
                "language": {
                    "code": WHATSAPP_TEMPLATE_OTP_LANGUAGE,
                },
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {
                                "type": "text",
                                "text": clean_code,
                            },
                        ],
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": "0",
                        "parameters": [
                            {
                                "type": "text",
                                "text": clean_code,
                            },
                        ],
                    },
                ],
            },
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(
                    cls.CONNECT_TIMEOUT_SECONDS,
                    cls.READ_TIMEOUT_SECONDS,
                ),
            )

        except requests.Timeout as exc:
            raise WhatsAppServiceError(
                "Délai WhatsApp Cloud API dépassé"
            ) from exc

        except requests.RequestException as exc:
            raise WhatsAppServiceError(
                "Connexion à WhatsApp Cloud API impossible"
            ) from exc

        try:
            response_data = response.json()

        except ValueError as exc:
            raise WhatsAppServiceError(
                "Réponse WhatsApp Cloud API invalide"
            ) from exc

        if not isinstance(response_data, dict):
            raise WhatsAppServiceError(
                "Format de réponse WhatsApp invalide"
            )

        if response.status_code not in {200, 201}:
            raise WhatsAppServiceError(
                cls._extract_error_message(response_data)
            )

        messages = response_data.get("messages")

        if not isinstance(messages, list) or not messages:
            raise WhatsAppServiceError(
                "Meta n'a retourné aucun identifiant de message"
            )

        first_message = messages[0]

        if not isinstance(first_message, dict):
            raise WhatsAppServiceError(
                "Réponse de message WhatsApp invalide"
            )

        message_id = str(
            first_message.get("id")
            or ""
        ).strip()

        if not message_id:
            raise WhatsAppServiceError(
                "Identifiant du message WhatsApp absent"
            )

        recipient_wa_id: str | None = None
        contacts = response_data.get("contacts")

        if isinstance(contacts, list) and contacts:
            first_contact = contacts[0]

            if isinstance(first_contact, dict):
                wa_id = str(
                    first_contact.get("wa_id")
                    or ""
                ).strip()

                recipient_wa_id = wa_id or None

        return WhatsAppMessageResult(
            message_id=message_id,
            recipient_wa_id=recipient_wa_id,
        )