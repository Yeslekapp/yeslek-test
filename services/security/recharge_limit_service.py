# ---------------------------
# Feature: Global Recharge Limit
# ---------------------------

from __future__ import annotations

import hashlib
import hmac
import os
from math import ceil
from typing import Any, Dict

from flask import current_app, has_app_context
from sqlalchemy import text

from db.database import SessionLocal


class RechargeLimitService:

    # ---------------------------
    # Configuration
    # ---------------------------

    MAX_RECHARGES = 3

    WINDOW_HOURS = 12

    RESERVATION_MINUTES = 60


    # ---------------------------
    # Phone privacy key
    # ---------------------------

    @staticmethod
    def _phone_key(
        phone: str,
    ) -> str:

        clean_phone = str(
            phone or ""
        ).strip()

        if not clean_phone:
            raise ValueError(
                "missing_phone"
            )

        secret = os.getenv(
            "RECHARGE_LIMIT_HMAC_SECRET"
        )

        if (
            not secret
            and has_app_context()
        ):
            secret = current_app.config.get(
                "SECRET_KEY"
            )

        if not secret:
            raise RuntimeError(
                "missing_recharge_limit_secret"
            )

        return hmac.new(
            str(secret).encode("utf-8"),
            clean_phone.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


    # ---------------------------
    # Current phone state
    # ---------------------------

    @classmethod
    def _get_state(
        cls,
        *,
        db,
        phone_key: str,
    ) -> Dict[str, Any]:

        row = db.execute(
            text(
                """
                SELECT
                    COUNT(*)::INTEGER AS active_count,

                    COALESCE(
                        EXTRACT(
                            EPOCH FROM (
                                MIN(expires_at) - NOW()
                            )
                        ),
                        0
                    ) AS retry_after_seconds

                FROM public.recharge_limit_events

                WHERE phone_key = :phone_key

                  AND status IN (
                      'RESERVED',
                      'SUCCESS'
                  )

                  AND expires_at > NOW()
                """
            ),
            {
                "phone_key": phone_key,
            },
        ).mappings().first()

        active_count = int(
            (
                row or {}
            ).get(
                "active_count",
                0,
            )
            or 0
        )

        retry_after_seconds = int(
            ceil(
                max(
                    float(
                        (
                            row or {}
                        ).get(
                            "retry_after_seconds",
                            0,
                        )
                        or 0
                    ),
                    0,
                )
            )
        )

        allowed = (
            active_count
            < cls.MAX_RECHARGES
        )

        return {
            "allowed": allowed,
            "count": active_count,
            "max_recharges": cls.MAX_RECHARGES,
            "window_hours": cls.WINDOW_HOURS,
            "retry_after_seconds": (
                0
                if allowed
                else retry_after_seconds
            ),
        }


    # ---------------------------
    # Public number check
    # ---------------------------

    @classmethod
    def check(
        cls,
        *,
        phone: str,
    ) -> Dict[str, Any]:

        phone_key = cls._phone_key(
            phone
        )

        db = SessionLocal()

        try:

            return cls._get_state(
                db=db,
                phone_key=phone_key,
            )

        finally:

            db.close()


    # ---------------------------
    # Atomic slot reservation
    # ---------------------------

    @classmethod
    def reserve(
        cls,
        *,
        phone: str,
        reservation_key: str,
    ) -> Dict[str, Any]:

        phone_key = cls._phone_key(
            phone
        )

        reservation_key = str(
            reservation_key or ""
        ).strip()

        if not reservation_key:
            raise ValueError(
                "missing_reservation_key"
            )

        db = SessionLocal()

        try:

            # ---------------------------
            # Atomic lock per phone
            # ---------------------------

            db.execute(
                text(
                    """
                    SELECT pg_advisory_xact_lock(
                        hashtext(:phone_key)
                    )
                    """
                ),
                {
                    "phone_key": phone_key,
                },
            )

            # ---------------------------
            # Existing idempotent slot
            # ---------------------------

            existing = db.execute(
                text(
                    """
                    SELECT
                        phone_key,
                        status

                    FROM public.recharge_limit_events

                    WHERE reservation_key = :reservation_key

                      AND status IN (
                          'RESERVED',
                          'SUCCESS'
                      )

                      AND expires_at > NOW()

                    LIMIT 1

                    FOR UPDATE
                    """
                ),
                {
                    "reservation_key": reservation_key,
                },
            ).mappings().first()

            if existing:

                if (
                    existing.get(
                        "phone_key"
                    )
                    != phone_key
                ):
                    raise RuntimeError(
                        "reservation_phone_mismatch"
                    )

                state = cls._get_state(
                    db=db,
                    phone_key=phone_key,
                )

                db.commit()

                return {
                    **state,
                    "allowed": True,
                    "already_reserved": True,
                    "reservation_key": reservation_key,
                }

            # ---------------------------
            # Check current global limit
            # ---------------------------

            state = cls._get_state(
                db=db,
                phone_key=phone_key,
            )

            if not state["allowed"]:

                db.commit()

                return {
                    **state,
                    "already_reserved": False,
                    "reservation_key": None,
                }

            # ---------------------------
            # Create temporary slot
            # ---------------------------

            db.execute(
                text(
                    """
                    INSERT INTO public.recharge_limit_events (
                        phone_key,
                        reservation_key,
                        status,
                        created_at,
                        updated_at,
                        expires_at
                    )

                    VALUES (
                        :phone_key,
                        :reservation_key,
                        'RESERVED',
                        NOW(),
                        NOW(),
                        NOW()
                        + (
                            :reservation_minutes
                            * INTERVAL '1 minute'
                        )
                    )

                    ON CONFLICT (
                        reservation_key
                    )

                    DO UPDATE SET
                        phone_key = EXCLUDED.phone_key,
                        payment_intent_id = NULL,
                        status = 'RESERVED',
                        updated_at = NOW(),
                        expires_at = (
                            NOW()
                            + (
                                :reservation_minutes
                                * INTERVAL '1 minute'
                            )
                        )
                    """
                ),
                {
                    "phone_key": phone_key,
                    "reservation_key": reservation_key,
                    "reservation_minutes": (
                        cls.RESERVATION_MINUTES
                    ),
                },
            )

            db.commit()

            return {
                "allowed": True,
                "count": (
                    state["count"]
                    + 1
                ),
                "max_recharges": (
                    cls.MAX_RECHARGES
                ),
                "window_hours": (
                    cls.WINDOW_HOURS
                ),
                "retry_after_seconds": 0,
                "already_reserved": False,
                "reservation_key": reservation_key,
            }

        except Exception:

            db.rollback()

            raise

        finally:

            db.close()


    # ---------------------------
    # Bind Stripe Payment Intent
    # ---------------------------

    @staticmethod
    def bind_payment_intent(
        *,
        reservation_key: str,
        payment_intent_id: str,
    ) -> None:

        reservation_key = str(
            reservation_key or ""
        ).strip()

        payment_intent_id = str(
            payment_intent_id or ""
        ).strip()

        if (
            not reservation_key
            or not payment_intent_id
        ):
            return

        db = SessionLocal()

        try:

            db.execute(
                text(
                    """
                    UPDATE public.recharge_limit_events

                    SET
                        payment_intent_id = :payment_intent_id,
                        updated_at = NOW()

                    WHERE reservation_key = :reservation_key

                      AND status = 'RESERVED'
                    """
                ),
                {
                    "reservation_key": reservation_key,
                    "payment_intent_id": payment_intent_id,
                },
            )

            db.commit()

        except Exception:

            db.rollback()

            raise

        finally:

            db.close()


    # ---------------------------
    # Confirm successful recharge
    # ---------------------------

    @classmethod
    def mark_success(
        cls,
        *,
        phone: str,
        reservation_key: str,
        payment_intent_id: str = "",
    ) -> None:

        phone_key = cls._phone_key(
            phone
        )

        reservation_key = str(
            reservation_key or ""
        ).strip()

        payment_intent_id = str(
            payment_intent_id or ""
        ).strip()

        if not reservation_key:
            return

        db = SessionLocal()

        try:

            db.execute(
                text(
                    """
                    SELECT pg_advisory_xact_lock(
                        hashtext(:phone_key)
                    )
                    """
                ),
                {
                    "phone_key": phone_key,
                },
            )

            db.execute(
                text(
                    """
                    INSERT INTO public.recharge_limit_events (
                        phone_key,
                        reservation_key,
                        payment_intent_id,
                        status,
                        created_at,
                        updated_at,
                        expires_at
                    )

                    VALUES (
                        :phone_key,
                        :reservation_key,
                        :payment_intent_id,
                        'SUCCESS',
                        NOW(),
                        NOW(),
                        NOW()
                        + (
                            :window_hours
                            * INTERVAL '1 hour'
                        )
                    )

                    ON CONFLICT (
                        reservation_key
                    )

                    DO UPDATE SET
                        phone_key = EXCLUDED.phone_key,
                        payment_intent_id = EXCLUDED.payment_intent_id,
                        status = 'SUCCESS',
                        updated_at = NOW(),
                        expires_at = (
                            NOW()
                            + (
                                :window_hours
                                * INTERVAL '1 hour'
                            )
                        )
                    """
                ),
                {
                    "phone_key": phone_key,
                    "reservation_key": reservation_key,
                    "payment_intent_id": (
                        payment_intent_id
                        or None
                    ),
                    "window_hours": (
                        cls.WINDOW_HOURS
                    ),
                },
            )

            db.commit()

        except Exception:

            db.rollback()

            raise

        finally:

            db.close()


    # ---------------------------
    # Release failed payment slot
    # ---------------------------

    @staticmethod
    def release(
        *,
        reservation_key: str,
    ) -> None:

        reservation_key = str(
            reservation_key or ""
        ).strip()

        if not reservation_key:
            return

        db = SessionLocal()

        try:

            db.execute(
                text(
                    """
                    UPDATE public.recharge_limit_events

                    SET
                        status = 'RELEASED',
                        updated_at = NOW(),
                        expires_at = NOW()

                    WHERE reservation_key = :reservation_key

                      AND status = 'RESERVED'
                    """
                ),
                {
                    "reservation_key": reservation_key,
                },
            )

            db.commit()

        except Exception:

            db.rollback()

            raise

        finally:

            db.close()