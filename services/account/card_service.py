# ---------------------------
# Card Service (FINAL SAFE)
# ---------------------------

import json
import os


CARDS_FILE = "data/saved_cards.json"


class CardService:

    # ---------------------------
    # Read cards
    # ---------------------------
    @staticmethod
    def _read_cards():

        if not os.path.exists(CARDS_FILE):
            return []

        try:

            with open(
                CARDS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                return json.load(f)

        except Exception:
            return []

    # ---------------------------
    # Write cards
    # ---------------------------
    @staticmethod
    def _write_cards(cards):

        os.makedirs("data", exist_ok=True)

        with open(
            CARDS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                cards,
                f,
                indent=2
            )

    # ---------------------------
    # Save card
    # ---------------------------
    @staticmethod
    def save_card(
        user_id: str,
        payment_method
    ):

        if not user_id or not payment_method:
            return

        cards = CardService._read_cards()

        # ---------------------------
        # Prevent duplicates
        # ---------------------------
        existing = next(
            (
                c for c in cards
                if (
                    c.get("id") == payment_method.id
                    and str(c.get("user_id")) == str(user_id)
                )
            ),
            None
        )

        if existing:
            return

        card = {

            "id": payment_method.id,

            "user_id": str(user_id),

            "brand": (
                payment_method.card.brand
                or "card"
            ),

            "last4": (
                payment_method.card.last4
            ),

            "expiry": (
                f"{payment_method.card.exp_month}/"
                f"{payment_method.card.exp_year}"
            ),

            "is_default": False,
        }

        cards.append(card)

        CardService._write_cards(cards)

    # ---------------------------
    # Get user cards
    # ---------------------------
    @staticmethod
    def get_user_cards(user_id: str):

        cards = CardService._read_cards()

        return [
            c for c in cards
            if str(c.get("user_id")) == str(user_id)
        ]

    # ---------------------------
    # Delete card
    # ---------------------------
    @staticmethod
    def delete_card(card_id: str):

        cards = CardService._read_cards()

        cards = [
            c for c in cards
            if c.get("id") != card_id
        ]

        CardService._write_cards(cards)