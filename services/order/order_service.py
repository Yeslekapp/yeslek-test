# ---------------------------
# OrderService — FINAL SAFE (NO BREAK)
# ---------------------------

import uuid
import json
import os
import re
from datetime import datetime


CARDS_FILE = "data/saved_cards.json"


class OrderService:

    # ---------------------------
    # Success payload
    # ---------------------------
    @staticmethod
    def build_success_payload(amount: str) -> dict:

        now = datetime.now()

        return {
            "amount": amount,
            "orderNumber": str(int(now.timestamp() * 1000)),
            "reference": uuid.uuid4().hex[:12].upper(),
            "date": now.strftime("%d/%m/%Y • %H:%M"),
        }

    # ---------------------------
    # Save card (tokenized mock)
    # ---------------------------
    @staticmethod
    def maybe_store_card_tokenized(
        user_id: str,
        save_card: bool,
        number: str,
        expiry: str
    ):

        if not save_card or not user_id:
            return

        digits = "".join(c for c in (number or "") if c.isdigit())

        if len(digits) < 4:
            return

        token = "tok_" + uuid.uuid4().hex[:16]
        last4 = digits[-4:]

        card = {
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "token": token,
            "last4": last4,
            "expiry": expiry,
            "brand": "card",
            "created_at": datetime.utcnow().isoformat(),
            "is_default": False,
        }

        OrderService._store_card(card)

    # ---------------------------
    # Internal storage
    # ---------------------------
    @staticmethod
    def _store_card(card):

        os.makedirs("data", exist_ok=True)

        cards = OrderService.get_saved_cards()
        cards.append(card)

        try:
            with open(CARDS_FILE, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2)
        except Exception as e:
            print("SAVE CARD ERROR:", e)

    # ---------------------------
    # Get saved cards
    # ---------------------------
    @staticmethod
    def get_saved_cards(user_id: str = None):

        if not os.path.exists(CARDS_FILE):
            return []

        try:
            with open(CARDS_FILE, "r", encoding="utf-8") as f:
                cards = json.load(f)

            if user_id:
                return [c for c in cards if c.get("user_id") == user_id]

            return cards

        except Exception as e:
            print("READ CARD ERROR:", e)
            return []

    # ---------------------------
    # Delete saved card
    # ---------------------------
    @staticmethod
    def delete_saved_card(user_id, card_id):

        cards = OrderService.get_saved_cards()

        cards = [
            c for c in cards
            if not (c["id"] == card_id and c.get("user_id") == user_id)
        ]

        try:
            with open(CARDS_FILE, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2)
        except Exception as e:
            print("DELETE CARD ERROR:", e)

    # ---------------------------
    # Get card
    # ---------------------------
    @staticmethod
    def get_saved_card(user_id, card_id):

        cards = OrderService.get_saved_cards(user_id)

        for c in cards:
            if c["id"] == card_id:
                return c

        return None

    # ---------------------------
    # Set default card (SAFE FIX)
    # ---------------------------
    @staticmethod
    def set_default_card(user_id, card_id):

        cards = OrderService.get_saved_cards()

        found = False

        for c in cards:
            if c.get("user_id") == user_id:
                if c["id"] == card_id:
                    c["is_default"] = True
                    found = True
                else:
                    c["is_default"] = False

        if not found:
            return  # sécurité

        try:
            with open(CARDS_FILE, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2)
        except Exception as e:
            print("DEFAULT CARD ERROR:", e)

    # ---------------------------
    # Update saved card
    # ---------------------------
    @staticmethod
    def update_saved_card(card_id: str, name: str, number: str, expiry: str):

        cards = OrderService.get_saved_cards()

        digits = re.sub(r"\D", "", number or "")
        last4 = digits[-4:] if len(digits) >= 4 else None

        for c in cards:
            if c["id"] == card_id:

                if name:
                    c["name"] = name

                if last4:
                    c["last4"] = last4

                if expiry:
                    c["expiry"] = expiry

        try:
            with open(CARDS_FILE, "w", encoding="utf-8") as f:
                json.dump(cards, f, indent=2)
        except Exception as e:
            print("UPDATE CARD ERROR:", e)