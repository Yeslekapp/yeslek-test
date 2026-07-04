# ---------------------------
# Stripe Service
# ---------------------------

from __future__ import annotations

import stripe
import config


stripe.api_key = config.STRIPE_SECRET_KEY


class StripeService:

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
            }
        }

        if email:
            params["email"] = email

        try:
            return stripe.Customer.create(
                **params
            )

        except Exception as e:
            print("❌ Stripe create_customer error:", e)
            raise
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

        intent = stripe.PaymentIntent.create(
            amount=int(round(float(amount) * 100)),
            currency=currency.lower(),
            customer=customer_id,
            payment_method=payment_method_id,
            confirm=True,
            payment_method_types=["card"],
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )

        return {
            "id": intent.id,
            "client_secret": intent.client_secret,
            "status": intent.status,
        }
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

        safe_amount = float(amount)

        if safe_amount < 0.50:
            raise ValueError("invalid_amount")

        if safe_amount > 80.00:
            raise ValueError("amount_too_high")

        unit_amount = int(
            round(safe_amount * 100)
        )

        params = {
            "amount": unit_amount,
            "currency": currency,
            "metadata": metadata or {},

            # ---------------------------
            # Customer display / bank label
            # ---------------------------
            "description": "Yeslek recharge mobile",
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

        if customer_email:
            params["receipt_email"] = customer_email

        # ---------------------------
        # Save card support
        # ---------------------------
        if customer_id:
            params["customer"] = customer_id

        if save_card and customer_id:
            params["setup_future_usage"] = "off_session"

        try:
            return stripe.PaymentIntent.create(
                **params,
                idempotency_key=idempotency_key,
            )

        except Exception as e:
            print("❌ Stripe create_payment_intent error:", e)
            raise

    # ---------------------------
    # Retrieve Payment Intent
    # ---------------------------
    @staticmethod
    def retrieve_payment(payment_id: str):

        try:
            return stripe.PaymentIntent.retrieve(
                payment_id
            )

        except Exception as e:
            print("❌ Stripe retrieve error:", e)
            raise

    # ---------------------------
    # Retrieve Payment Method
    # ---------------------------
    @staticmethod
    def retrieve_payment_method(payment_method_id: str):

        try:
            return stripe.PaymentMethod.retrieve(
                payment_method_id
            )

        except Exception as e:
            print("❌ Stripe retrieve payment method error:", e)
            raise

    # ---------------------------
    # Construct Webhook Event
    # ---------------------------
    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str):

        try:
            return stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=config.STRIPE_WEBHOOK_SECRET,
            )

        except stripe.error.SignatureVerificationError as e:
            print("❌ Stripe signature verification failed:", e)
            raise

        except ValueError as e:
            print("❌ Stripe invalid payload:", e)
            raise

        except Exception as e:
            print("❌ Stripe webhook unknown error:", e)
            raise