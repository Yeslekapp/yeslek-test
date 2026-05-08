# ---------------------------
# Stripe Service
# ---------------------------

import stripe
import config


stripe.api_key = config.STRIPE_SECRET_KEY


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

        safe_amount = max(float(amount), 0.50)
        unit_amount = int(round(safe_amount * 100))

        try:
            intent = stripe.PaymentIntent.create(
                amount=unit_amount,
                currency=currency,
                metadata=metadata or {},

                # ✅ IMPORTANT FIX CB + VISA + MASTERCARD
                automatic_payment_methods={"enabled": True},
            )

            return intent

        except Exception as e:
            print("❌ Stripe create_payment_intent error:", e)
            raise

    # ---------------------------
    # Retrieve Payment Intent
    # ---------------------------
    @staticmethod
    def retrieve_payment(payment_id: str):

        try:
            return stripe.PaymentIntent.retrieve(payment_id)

        except Exception as e:
            print("❌ Stripe retrieve error:", e)
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