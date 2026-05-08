# ---------------------------
# services/stripe/stripe_service.py
# ---------------------------

import logging

import stripe
import config


# ---------------------------
# Stripe config
# ---------------------------
stripe.api_key = config.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


# ---------------------------
# Stripe Service
# ---------------------------
class StripeService:

    # ---------------------------
    # Create Payment Intent
    # ---------------------------
    @staticmethod
    def create_payment_intent(
        amount: float,
        currency: str = "eur",
        metadata: dict | None = None,
    ):

        # ---------------------------
        # Safe amount
        # ---------------------------
        safe_amount = max(
            float(amount),
            0.50,
        )

        unit_amount = int(
            round(safe_amount * 100)
        )

        try:

            intent = stripe.PaymentIntent.create(

                # ---------------------------
                # Core
                # ---------------------------
                amount=unit_amount,
                currency=currency.lower(),

                # ---------------------------
                # Metadata
                # ---------------------------
                metadata=metadata or {},

                # ---------------------------
                # Auto payments
                # ---------------------------
                automatic_payment_methods={
                    "enabled": True
                },

                # ---------------------------
                # Production protections
                # ---------------------------
                capture_method="automatic",
                confirmation_method="automatic",
            )

            return intent

        except stripe.error.CardError as e:

            logger.exception(
                "❌ Stripe card error: %s",
                e,
            )

            raise

        except stripe.error.StripeError as e:

            logger.exception(
                "❌ Stripe API error: %s",
                e,
            )

            raise

        except Exception as e:

            logger.exception(
                "❌ Stripe create_payment_intent unknown error: %s",
                e,
            )

            raise

    # ---------------------------
    # Retrieve Payment Intent
    # ---------------------------
    @staticmethod
    def retrieve_payment(
        payment_id: str
    ):

        try:

            return stripe.PaymentIntent.retrieve(
                payment_id
            )

        except stripe.error.StripeError as e:

            logger.exception(
                "❌ Stripe retrieve error: %s",
                e,
            )

            raise

        except Exception as e:

            logger.exception(
                "❌ Stripe unknown retrieve error: %s",
                e,
            )

            raise

    # ---------------------------
    # Retrieve Payment Method
    # ---------------------------
    @staticmethod
    def retrieve_payment_method(
        payment_method_id: str
    ):

        try:

            return stripe.PaymentMethod.retrieve(
                payment_method_id
            )

        except stripe.error.StripeError as e:

            logger.exception(
                "❌ Stripe payment method retrieve error: %s",
                e,
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

        except stripe.error.SignatureVerificationError as e:

            logger.exception(
                "❌ Stripe signature verification failed: %s",
                e,
            )

            raise

        except ValueError as e:

            logger.exception(
                "❌ Stripe invalid payload: %s",
                e,
            )

            raise

        except Exception as e:

            logger.exception(
                "❌ Stripe webhook unknown error: %s",
                e,
            )

            raise