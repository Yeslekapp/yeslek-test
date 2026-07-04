# ---------------------------
# Card Service (POSTGRESQL SAFE)
# ---------------------------

from __future__ import annotations

from typing import Any, Optional

from services.core.db_service import db_cursor
from services.stripe.stripe_service import StripeService


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
    # Row mapper
    # ---------------------------
    @staticmethod
    def _card_from_row(
        row: dict,
    ) -> dict:

        return {
            "id": row.get("payment_method_id"),
            "card_id": row.get("payment_method_id"),
            "db_id": row.get("id"),
            "user_id": str(row.get("user_id")),
            "stripe_customer_id": row.get("stripe_customer_id") or "",
            "brand": row.get("brand") or "card",
            "last4": row.get("last4") or "",
            "exp_month": row.get("exp_month"),
            "exp_year": row.get("exp_year"),
            "expiry": row.get("expiry") or "",
            "fingerprint": row.get("fingerprint") or "",
            "is_default": bool(row.get("is_default")),
        }

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

        user_id = str(user_id)

        with db_cursor(commit=True) as cur:

            cur.execute(
                """
                SELECT stripe_customer_id
                FROM stripe_customers
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            existing = cur.fetchone()

            if existing and existing.get("stripe_customer_id"):
                return str(existing["stripe_customer_id"])

            customer = StripeService.create_customer(
                email=email,
                user_id=user_id,
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

            cur.execute(
                """
                INSERT INTO stripe_customers (
                    user_id,
                    email,
                    stripe_customer_id
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    email = EXCLUDED.email,
                    stripe_customer_id = EXCLUDED.stripe_customer_id,
                    updated_at = NOW()
                RETURNING stripe_customer_id
                """,
                (
                    user_id,
                    email or "",
                    stripe_customer_id,
                ),
            )

            row = cur.fetchone()

            return str(row["stripe_customer_id"])

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

        user_id = str(user_id)

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

        expiry = f"{int(exp_month):02d}/{int(exp_year)}"

        with db_cursor(commit=True) as cur:

            cur.execute(
                """
                SELECT id
                FROM saved_cards
                WHERE user_id = %s
                  AND deleted_at IS NULL
                LIMIT 1
                """,
                (user_id,),
            )

            has_existing_card = cur.fetchone() is not None
            is_default = not has_existing_card

            cur.execute(
                """
                SELECT *
                FROM saved_cards
                WHERE user_id = %s
                  AND deleted_at IS NULL
                  AND (
                    payment_method_id = %s
                    OR (
                        %s <> ''
                        AND fingerprint = %s
                    )
                  )
                LIMIT 1
                """,
                (
                    user_id,
                    payment_method_id,
                    fingerprint,
                    fingerprint,
                ),
            )

            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE saved_cards
                    SET
                        stripe_customer_id = COALESCE(NULLIF(%s, ''), stripe_customer_id),
                        brand = %s,
                        last4 = %s,
                        exp_month = %s,
                        exp_year = %s,
                        expiry = %s,
                        fingerprint = NULLIF(%s, ''),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        stripe_customer_id or "",
                        brand,
                        last4,
                        int(exp_month),
                        int(exp_year),
                        expiry,
                        fingerprint,
                        existing["id"],
                    ),
                )

                row = cur.fetchone()

                return CardService._card_from_row(row)

            cur.execute(
                """
                INSERT INTO saved_cards (
                    user_id,
                    stripe_customer_id,
                    payment_method_id,
                    brand,
                    last4,
                    exp_month,
                    exp_year,
                    expiry,
                    fingerprint,
                    is_default
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULLIF(%s, ''), %s)
                RETURNING *
                """,
                (
                    user_id,
                    stripe_customer_id or "",
                    payment_method_id,
                    brand,
                    last4,
                    int(exp_month),
                    int(exp_year),
                    expiry,
                    fingerprint,
                    is_default,
                ),
            )

            row = cur.fetchone()

            return CardService._card_from_row(row)

    # ---------------------------
    # Get user cards
    # ---------------------------
    @staticmethod
    def get_user_cards(
        user_id: str,
    ) -> list[dict]:

        if not user_id:
            return []

        with db_cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM saved_cards
                WHERE user_id = %s
                  AND deleted_at IS NULL
                ORDER BY is_default DESC, created_at DESC
                """,
                (str(user_id),),
            )

            rows = cur.fetchall() or []

        return [
            CardService._card_from_row(row)
            for row in rows
        ]

    # ---------------------------
    # Compatibility: Flutter naming
    # ---------------------------
    @staticmethod
    def get_saved_cards(
        user_id: str,
    ) -> list[dict]:

        return CardService.get_user_cards(
            user_id
        )

    # ---------------------------
    # Get card
    # ---------------------------
    @staticmethod
    def get_card(
        *,
        user_id: str,
        card_id: str,
    ) -> Optional[dict]:

        if not user_id or not card_id:
            return None

        with db_cursor() as cur:

            cur.execute(
                """
                SELECT *
                FROM saved_cards
                WHERE user_id = %s
                  AND payment_method_id = %s
                  AND deleted_at IS NULL
                LIMIT 1
                """,
                (
                    str(user_id),
                    str(card_id),
                ),
            )

            row = cur.fetchone()

        if not row:
            return None

        return CardService._card_from_row(row)

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

        user_id = str(user_id)
        card_id = str(card_id)

        with db_cursor(commit=True) as cur:

            cur.execute(
                """
                SELECT id
                FROM saved_cards
                WHERE user_id = %s
                  AND payment_method_id = %s
                  AND deleted_at IS NULL
                LIMIT 1
                """,
                (
                    user_id,
                    card_id,
                ),
            )

            target = cur.fetchone()

            if not target:
                return False

            cur.execute(
                """
                UPDATE saved_cards
                SET
                    is_default = FALSE,
                    updated_at = NOW()
                WHERE user_id = %s
                  AND deleted_at IS NULL
                """,
                (user_id,),
            )

            cur.execute(
                """
                UPDATE saved_cards
                SET
                    is_default = TRUE,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (target["id"],),
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

        with db_cursor(commit=True) as cur:

            cur.execute(
                """
                SELECT *
                FROM saved_cards
                WHERE payment_method_id = %s
                  AND deleted_at IS NULL
                  AND (
                    %s IS NULL
                    OR user_id = %s
                  )
                LIMIT 1
                """,
                (
                    str(card_id),
                    str(user_id) if user_id else None,
                    str(user_id) if user_id else None,
                ),
            )

            card = cur.fetchone()

            if not card:
                return False

            was_default = bool(card.get("is_default"))
            card_user_id = str(card.get("user_id"))

            cur.execute(
                """
                UPDATE saved_cards
                SET
                    deleted_at = NOW(),
                    is_default = FALSE,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (card["id"],),
            )

            if was_default:
                cur.execute(
                    """
                    SELECT id
                    FROM saved_cards
                    WHERE user_id = %s
                      AND deleted_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (card_user_id,),
                )

                next_card = cur.fetchone()

                if next_card:
                    cur.execute(
                        """
                        UPDATE saved_cards
                        SET
                            is_default = TRUE,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (next_card["id"],),
                    )

        return True

    # ---------------------------
    # Compatibility: Flutter naming
    # ---------------------------
    @staticmethod
    def delete_saved_card(
        user_id: str,
        card_id: str,
    ) -> bool:

        return CardService.delete_card(
            card_id=card_id,
            user_id=str(user_id),
        )