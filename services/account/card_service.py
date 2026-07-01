# ---------------------------
# Card Service (FINAL SAFE)
# ---------------------------

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Optional

from services.stripe.stripe_service import StripeService


CARDS_FILE = "data/saved_cards.json"
CUSTOMERS_FILE = "data/stripe_customers.json"


class CardService:

    # ---------------------------
    # Safe getter
    # ---------------------------
    @staticmethod
    def _get_value(
        obj: Any,
        key: str,
        default: Any = None,
    ) -> Any:

        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    # ---------------------------
    # Read JSON
    # ---------------------------
    @staticmethod
    def _read_json(path: str) -> list[dict]:

        if not os.path.exists(path):
            return []

        try:
            with open(
                path,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            if isinstance(data, list):
                return data

            return []

        except Exception:
            return []

    # ---------------------------
    # Write JSON atomic
    # ---------------------------
    @staticmethod
    def _write_json(
        path: str,
        data: list[dict],
    ) -> None:

        os.makedirs(
            os.path.dirname(path),
            exist_ok=True,
        )

        directory = os.path.dirname(path)

        fd, temp_path = tempfile.mkstemp(
            dir=directory,
            prefix=".tmp_",
            suffix=".json",
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            os.replace(
                temp_path,
                path,
            )

        except Exception:
            try:
                os.remove(temp_path)
            except Exception:
                pass

            raise

    # ---------------------------
    # Read cards
    # ---------------------------
    @staticmethod
    def _read_cards() -> list[dict]:

        return CardService._read_json(
            CARDS_FILE
        )

    # ---------------------------
    # Write cards
    # ---------------------------
    @staticmethod
    def _write_cards(
        cards: list[dict],
    ) -> None:

        CardService._write_json(
            CARDS_FILE,
            cards,
        )

    # ---------------------------
    # Read customers
    # ---------------------------
    @staticmethod
    def _read_customers() -> list[dict]:

        return CardService._read_json(
            CUSTOMERS_FILE
        )

    # ---------------------------
    # Write customers
    # ---------------------------
    @staticmethod
    def _write_customers(
        customers: list[dict],
    ) -> None:

        CardService._write_json(
            CUSTOMERS_FILE,
            customers,
        )

    # ---------------------------
    # Get or create Stripe customer
    # ---------------------------
    @staticmethod
    def get_or_create_stripe_customer_id(
        *,
        user_id: str,
        email: Optional[str] = None,
    ) -> str:

        if not user_id:
            raise ValueError("missing_user_id")

        customers = CardService._read_customers()

        existing = next(
            (
                customer
                for customer in customers
                if str(customer.get("user_id")) == str(user_id)
                and customer.get("stripe_customer_id")
            ),
            None,
        )

        if existing:
            return str(
                existing.get("stripe_customer_id")
            )

        customer = StripeService.create_customer(
            email=email,
            user_id=str(user_id),
        )

        stripe_customer_id = str(
            CardService._get_value(
                customer,
                "id",
                "",
            )
        )

        if not stripe_customer_id:
            raise ValueError("missing_stripe_customer_id")

        customers.append(
            {
                "user_id": str(user_id),
                "email": email or "",
                "stripe_customer_id": stripe_customer_id,
            }
        )

        CardService._write_customers(
            customers
        )

        return stripe_customer_id

    # ---------------------------
    # Save card
    # ---------------------------
    @staticmethod
    def save_card(
        user_id: str,
        payment_method: Any,
        stripe_customer_id: Optional[str] = None,
    ) -> Optional[dict]:

        if not user_id or not payment_method:
            return None

        payment_method_id = str(
            CardService._get_value(
                payment_method,
                "id",
                "",
            )
        )

        if not payment_method_id:
            return None

        card_data = CardService._get_value(
            payment_method,
            "card",
        )

        if not card_data:
            return None

        brand = str(
            CardService._get_value(
                card_data,
                "brand",
                "card",
            )
            or "card"
        )

        last4 = str(
            CardService._get_value(
                card_data,
                "last4",
                "",
            )
            or ""
        )

        exp_month = CardService._get_value(
            card_data,
            "exp_month",
            "",
        )

        exp_year = CardService._get_value(
            card_data,
            "exp_year",
            "",
        )

        fingerprint = str(
            CardService._get_value(
                card_data,
                "fingerprint",
                "",
            )
            or ""
        )

        if not last4 or not exp_month or not exp_year:
            return None

        cards = CardService._read_cards()

        user_cards = [
            card
            for card in cards
            if str(card.get("user_id")) == str(user_id)
        ]

        # ---------------------------
        # Prevent duplicates
        # ---------------------------
        existing = next(
            (
                card
                for card in user_cards
                if card.get("id") == payment_method_id
                or (
                    fingerprint
                    and card.get("fingerprint") == fingerprint
                )
            ),
            None,
        )

        if existing:
            return existing

        is_default = len(user_cards) == 0

        card = {
            "id": payment_method_id,
            "user_id": str(user_id),
            "stripe_customer_id": stripe_customer_id or "",
            "brand": brand,
            "last4": last4,
            "exp_month": int(exp_month),
            "exp_year": int(exp_year),
            "expiry": f"{exp_month}/{exp_year}",
            "fingerprint": fingerprint,
            "is_default": is_default,
        }

        cards.append(card)

        CardService._write_cards(
            cards
        )

        return card

    # ---------------------------
    # Get user cards
    # ---------------------------
    @staticmethod
    def get_user_cards(
        user_id: str,
    ) -> list[dict]:

        if not user_id:
            return []

        cards = CardService._read_cards()

        return [
            card
            for card in cards
            if str(card.get("user_id")) == str(user_id)
        ]

    # ---------------------------
    # Get card
    # ---------------------------
    @staticmethod
    def get_card(
        *,
        user_id: str,
        card_id: str,
    ) -> Optional[dict]:

        cards = CardService.get_user_cards(
            user_id
        )

        return next(
            (
                card
                for card in cards
                if card.get("id") == card_id
            ),
            None,
        )

    # ---------------------------
    # Set default card
    # ---------------------------
    @staticmethod
    def set_default_card(
        *,
        user_id: str,
        card_id: str,
    ) -> bool:

        if not user_id or not card_id:
            return False

        cards = CardService._read_cards()

        found = False

        for card in cards:
            if str(card.get("user_id")) != str(user_id):
                continue

            is_target = card.get("id") == card_id

            card["is_default"] = is_target

            if is_target:
                found = True

        if not found:
            return False

        CardService._write_cards(
            cards
        )

        return True

    # ---------------------------
    # Delete card
    # ---------------------------
    @staticmethod
    def delete_card(
        card_id: str,
        user_id: Optional[str] = None,
    ) -> bool:

        if not card_id:
            return False

        cards = CardService._read_cards()

        old_count = len(cards)

        cards = [
            card
            for card in cards
            if not (
                card.get("id") == card_id
                and (
                    user_id is None
                    or str(card.get("user_id")) == str(user_id)
                )
            )
        ]

        deleted = len(cards) != old_count

        if deleted:
            CardService._write_cards(
                cards
            )

        return deleted