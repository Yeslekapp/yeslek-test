# ---------------------------
# Stripe Service
# ---------------------------

from __future__ import annotations

import logging

import stripe

import config


stripe.api_key = config.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


class StripeService:

    # ---------------------------
    # Helpers
    # ---------------------------

    @staticmethod
    def _safe_str(value) -> str:

        if value is None:
            return ""

        return str(value).strip()
    @staticmethod
    def _payment_description(
        metadata: dict | None,
    ) -> str:

        metadata = metadata or {}

        payment_channel = (
            StripeService._safe_str(metadata.get("payment_channel"))
            or StripeService._safe_str(metadata.get("payment_method"))
            or "card"
        )

        paid_amount = (
            StripeService._safe_str(metadata.get("charged_amount"))
            or StripeService._safe_str(metadata.get("total"))
            or StripeService._safe_str(metadata.get("recharge_amount"))
        )

        user_email = (
            StripeService._safe_str(metadata.get("user_email"))
            or StripeService._safe_str(metadata.get("email"))
        )

        phone = StripeService._safe_str(
            metadata.get("recharge_phone")
        )

        country_iso = StripeService._safe_str(
            metadata.get("country_iso")
        )

        parts = [
            f"Mode: {payment_channel}",
        ]

        if paid_amount:
            parts.append(
                f"Payé: {paid_amount} EUR"
            )

        if user_email:
            parts.append(
                f"Client: {user_email}"
            )

        elif phone:
            client_label = phone

            if country_iso:
                client_label = f"{phone} {country_iso}"

            parts.append(
                f"Client: {client_label}"
            )

        return " • ".join(parts)

    @staticmethod
    def _is_no_such_customer_error(exc: Exception) -> bool:

        message = str(exc or "").lower()

        return (
            "no such customer" in message
            or "resource_missing" in message
        )


    @staticmethod
    def _payment_intent_payload(intent) -> dict:

        return {
            "id": getattr(intent, "id", ""),
            "client_secret": getattr(intent, "client_secret", ""),
            "status": getattr(intent, "status", ""),
            "customer": StripeService._safe_str(
                getattr(intent, "customer", "")
            ),
        }


    # ---------------------------
    # Create Customer
    # ---------------------------

    @staticmethod
    def create_customer(
        *,
        email: str | None = None,
        user_id: str | None = None,
    ):

        params = {
            "metadata": {
                "user_id": str(user_id or ""),
                "source": "yeslek",
            }
        }

        if email:
            params["email"] = email

        try:
            return stripe.Customer.create(
                **params
            )

        except Exception as exc:
            logger.exception(
                "Stripe create_customer error: %s",
                exc,
            )
            raise


    # ---------------------------
    # Retrieve Customer
    # ---------------------------

    @staticmethod
    def retrieve_customer(
        customer_id: str,
    ):

        customer_id = StripeService._safe_str(
            customer_id
        )

        if not customer_id:
            return None

        try:
            customer = stripe.Customer.retrieve(
                customer_id
            )

            if getattr(customer, "deleted", False):
                return None

            return customer

        except Exception as exc:

            if StripeService._is_no_such_customer_error(exc):
                return None

            raise


    # ---------------------------
    # Ensure Customer
    # ---------------------------

    @staticmethod
    def ensure_customer(
        *,
        customer_id: str | None = None,
        email: str | None = None,
        user_id: str | None = None,
    ) -> str:

        customer_id = StripeService._safe_str(
            customer_id
        )

        if customer_id:
            customer = StripeService.retrieve_customer(
                customer_id
            )

            if customer:
                return customer.id

            logger.warning(
                "Stripe customer missing in current mode | customer_id=%s | user_id=%s",
                customer_id,
                user_id,
            )

        customer = StripeService.create_customer(
            email=email,
            user_id=user_id,
        )

        return customer.id


    # ---------------------------
    # Saved card payment intent
    # ---------------------------

    @staticmethod
    def create_saved_card_payment_intent(
        *,
        amount: float,
        currency: str,
        payment_method_id: str,
        metadata: dict | None = None,
        customer_id: str,
        idempotency_key: str | None = None,
    ) -> dict:

        if not amount or float(amount) <= 0:
            raise ValueError("invalid_amount")

        if not payment_method_id:
            raise ValueError("missing_payment_method_id")

        if not customer_id:
            raise ValueError("missing_customer_id")

        valid_customer = StripeService.retrieve_customer(
            customer_id
        )

        if not valid_customer:
            raise ValueError("invalid_saved_card_customer")

        clean_metadata = dict(
            metadata or {}
        )

        clean_metadata["stripe_customer_id"] = valid_customer.id

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(round(float(amount) * 100)),
                currency=currency.lower(),
                customer=valid_customer.id,
                payment_method=payment_method_id,
                confirm=True,
                payment_method_types=["card"],
                metadata=clean_metadata,
                description=StripeService._payment_description(
                    clean_metadata
                ),
                idempotency_key=idempotency_key,
            )

            return StripeService._payment_intent_payload(
                intent
            )

        except Exception as exc:
            logger.exception(
                "Stripe saved card payment intent error: %s",
                exc,
            )
            raise


    # ---------------------------
    # Create Payment Intent
    # ---------------------------

    @staticmethod
    def create_payment_intent(
        amount: float,
        currency: str = "eur",
        metadata: dict | None = None,
        idempotency_key: str | None = None,
        customer_email: str | None = None,
        customer_id: str | None = None,
        save_card: bool = False,
    ):

        safe_amount = float(
            amount
        )

        if safe_amount < 0.50:
            raise ValueError("invalid_amount")

        if safe_amount > 80.00:
            raise ValueError("amount_too_high")

        unit_amount = int(
            round(safe_amount * 100)
        )

        clean_metadata = dict(
            metadata or {}
        )

        user_id = StripeService._safe_str(
            clean_metadata.get("user_id")
        )

        valid_customer_id = None

        if save_card:
            valid_customer_id = StripeService.ensure_customer(
                customer_id=customer_id,
                email=customer_email,
                user_id=user_id,
            )

            clean_metadata["stripe_customer_id"] = valid_customer_id

        elif customer_id:
            customer = StripeService.retrieve_customer(
                customer_id
            )

            if customer:
                valid_customer_id = customer.id
                clean_metadata["stripe_customer_id"] = valid_customer_id

        params = {
            "amount": unit_amount,
            "currency": currency.lower(),
            "metadata": clean_metadata,

            # ---------------------------
            # Customer display / bank label
            # ---------------------------
            "description": StripeService._payment_description(
                clean_metadata
            ),
            "statement_descriptor_suffix": "RECHARGE",

            # ---------------------------
            # Payment methods
            # ---------------------------
            "automatic_payment_methods": {
                "enabled": True,
            },

            # ---------------------------
            # Card testing protection
            # ---------------------------
            "payment_method_options": {
                "card": {
                    "request_three_d_secure": "automatic",
                }
            },
        }

        if valid_customer_id:
            params["customer"] = valid_customer_id

        if save_card and valid_customer_id:
            params["setup_future_usage"] = "off_session"

        try:
            return stripe.PaymentIntent.create(
                **params,
                idempotency_key=idempotency_key,
            )

        except Exception as exc:

            if (
                save_card
                and customer_id
                and StripeService._is_no_such_customer_error(exc)
            ):

                logger.warning(
                    "Stripe customer disappeared before PaymentIntent create | customer_id=%s | user_id=%s",
                    customer_id,
                    user_id,
                )

                fresh_customer = StripeService.create_customer(
                    email=customer_email,
                    user_id=user_id,
                )

                clean_metadata["stripe_customer_id"] = fresh_customer.id

                params["customer"] = fresh_customer.id
                params["metadata"] = clean_metadata
                params["setup_future_usage"] = "off_session"

                return stripe.PaymentIntent.create(
                    **params,
                    idempotency_key=idempotency_key,
                )

            logger.exception(
                "Stripe create_payment_intent error: %s",
                exc,
            )
            raise


    # ---------------------------
    # Retrieve Payment Intent
    # ---------------------------

    @staticmethod
    def retrieve_payment(
        payment_id: str,
    ):

        try:
            return stripe.PaymentIntent.retrieve(
                payment_id
            )

        except Exception as exc:
            logger.exception(
                "Stripe retrieve error: %s",
                exc,
            )
            raise


    # ---------------------------
    # Retrieve Payment Method
    # ---------------------------

    @staticmethod
    def retrieve_payment_method(
        payment_method_id: str,
    ):

        try:
            return stripe.PaymentMethod.retrieve(
                payment_method_id
            )

        except Exception as exc:
            logger.exception(
                "Stripe retrieve payment method error: %s",
                exc,
            )
            raise


    # ---------------------------
    # Construct Webhook Event
    # ---------------------------

    @staticmethod
    def construct_webhook_event(
        payload: bytes,
        sig_header: str,
    ):

        try:
            return stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=config.STRIPE_WEBHOOK_SECRET,
            )

        except Exception as exc:
            logger.exception(
                "Stripe webhook error: %s",
                exc,
            )
            raise