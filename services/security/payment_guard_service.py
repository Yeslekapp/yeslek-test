# ---------------------------
# Feature: Payment Guard Service
# ---------------------------

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from typing import Any, Dict, List, Tuple

from flask import request
from sqlalchemy import text

import config
from db.database import engine


class PaymentGuardError(Exception):

    def __init__(self, code: str, status_code: int = 429):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class PaymentGuardService:

    # ---------------------------
    # Limits
    # ---------------------------
    MAX_FINAL_AMOUNT = 80.00

    _TABLE_READY = False

    # ---------------------------
    # Database
    # ---------------------------
    @classmethod
    def _ensure_table(cls) -> None:

        if cls._TABLE_READY:
            return

        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS payment_risk_events (
                    id TEXT PRIMARY KEY,
                    event_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at BIGINT NOT NULL,
                    blocked_until BIGINT NULL
                )
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_payment_risk_events_key_time
                ON payment_risk_events (event_key, event_type, created_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_payment_risk_events_blocked
                ON payment_risk_events (event_key, blocked_until)
            """))

        cls._TABLE_READY = True

    # ---------------------------
    # Hashing
    # ---------------------------
    @staticmethod
    def _secret() -> bytes:

        secret = (
            getattr(config, "SECRET_KEY", None)
            or os.getenv("FLASK_SECRET_KEY")
            or "yeslek-payment-guard"
        )

        return str(secret).encode("utf-8")

    @classmethod
    def hash_value(cls, value: Any) -> str:

        raw = str(value or "").strip().lower()

        if not raw:
            raw = "unknown"

        return hmac.new(
            cls._secret(),
            raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:32]

    # ---------------------------
    # Request context
    # ---------------------------
    @staticmethod
    def client_ip() -> str:

        forwarded_for = request.headers.get("X-Forwarded-For", "")

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.access_route:
            return request.access_route[0]

        return request.remote_addr or "unknown"

    @staticmethod
    def user_agent() -> str:

        return request.headers.get("User-Agent", "unknown")[:300]

    # ---------------------------
    # Cleanup
    # ---------------------------
    @classmethod
    def _cleanup(cls, now: int) -> None:

        old = now - 86400

        with engine.begin() as conn:
            conn.execute(
                text("""
                    DELETE FROM payment_risk_events
                    WHERE created_at < :old
                    AND (
                        blocked_until IS NULL
                        OR blocked_until < :now
                    )
                """),
                {
                    "old": old,
                    "now": now,
                },
            )

    # ---------------------------
    # Block state
    # ---------------------------
    @classmethod
    def _blocked_until(cls, event_key: str, now: int) -> int:

        with engine.begin() as conn:
            value = conn.execute(
                text("""
                    SELECT COALESCE(MAX(blocked_until), 0)
                    FROM payment_risk_events
                    WHERE event_key = :event_key
                    AND blocked_until IS NOT NULL
                    AND blocked_until > :now
                """),
                {
                    "event_key": event_key,
                    "now": now,
                },
            ).scalar()

        return int(value or 0)

    @classmethod
    def _insert_event(
        cls,
        *,
        event_key: str,
        event_type: str,
        created_at: int,
        blocked_until: int | None = None,
    ) -> None:

        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO payment_risk_events (
                        id,
                        event_key,
                        event_type,
                        created_at,
                        blocked_until
                    )
                    VALUES (
                        :id,
                        :event_key,
                        :event_type,
                        :created_at,
                        :blocked_until
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "event_key": event_key,
                    "event_type": event_type,
                    "created_at": created_at,
                    "blocked_until": blocked_until,
                },
            )

    @classmethod
    def _count_events(
        cls,
        *,
        event_key: str,
        event_type: str,
        since: int,
    ) -> int:

        with engine.begin() as conn:
            value = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM payment_risk_events
                    WHERE event_key = :event_key
                    AND event_type = :event_type
                    AND created_at >= :since
                """),
                {
                    "event_key": event_key,
                    "event_type": event_type,
                    "since": since,
                },
            ).scalar()

        return int(value or 0)

    @classmethod
    def _register_and_check(
        cls,
        *,
        event_key: str,
        event_type: str,
        limit: int,
        window_seconds: int,
        block_seconds: int,
        now: int,
    ) -> None:

        blocked_until = cls._blocked_until(
            event_key,
            now,
        )

        if blocked_until > now:
            raise PaymentGuardError(
                "too_many_payment_attempts",
                429,
            )

        cls._insert_event(
            event_key=event_key,
            event_type=event_type,
            created_at=now,
        )

        count = cls._count_events(
            event_key=event_key,
            event_type=event_type,
            since=now - window_seconds,
        )

        if count > limit:

            cls._insert_event(
                event_key=event_key,
                event_type="blocked",
                created_at=now,
                blocked_until=now + block_seconds,
            )

            raise PaymentGuardError(
                "too_many_payment_attempts",
                429,
            )

    # ---------------------------
    # Payment create protection
    # ---------------------------
    @classmethod
    def assert_allowed(
        cls,
        *,
        phone: str,
        user_id: str | int | None,
        user_email: str | None,
        amount: float,
    ) -> Dict[str, Dict[str, str]]:

        cls._ensure_table()

        now = int(time.time())

        cls._cleanup(now)

        try:
            safe_amount = float(amount)
        except Exception:
            raise PaymentGuardError(
                "invalid_amount",
                400,
            )

        if safe_amount <= 0 or safe_amount > cls.MAX_FINAL_AMOUNT:
            raise PaymentGuardError(
                "invalid_amount",
                400,
            )

        ip_hash = cls.hash_value(
            cls.client_ip()
        )

        ua_hash = cls.hash_value(
            cls.user_agent()
        )

        phone_hash = cls.hash_value(
            phone
        )

        user_hash = cls.hash_value(
            user_id
        ) if user_id else ""

        email_hash = cls.hash_value(
            user_email
        ) if user_email else ""

        amount_key = f"{safe_amount:.2f}"

        # ---------------------------
        # 5 attempts / 5 minutes / block 24h
        # ---------------------------
        max_attempts = 5
        window_seconds = 300
        block_seconds = 86400

        checks: List[Tuple[str, int, int, int]] = [
            (
                f"payment:ip:{ip_hash}",
                max_attempts,
                window_seconds,
                block_seconds,
            ),
            (
                f"payment:ip_ua:{ip_hash}:{ua_hash}",
                max_attempts,
                window_seconds,
                block_seconds,
            ),
            (
                f"payment:ip_amount:{ip_hash}:{amount_key}",
                max_attempts,
                window_seconds,
                block_seconds,
            ),
        ]

        if user_hash:
            checks.append(
                (
                    f"payment:user:{user_hash}",
                    max_attempts,
                    window_seconds,
                    block_seconds,
                )
            )

        if email_hash:
            checks.append(
                (
                    f"payment:email:{email_hash}",
                    max_attempts,
                    window_seconds,
                    block_seconds,
                )
            )

        if phone:
            checks.append(
                (
                    f"payment:phone:{phone_hash}",
                    max_attempts,
                    window_seconds,
                    block_seconds,
                )
            )

        for event_key, limit, window_seconds, block_seconds in checks:
            cls._register_and_check(
                event_key=event_key,
                event_type="payment_create",
                limit=limit,
                window_seconds=window_seconds,
                block_seconds=block_seconds,
                now=now,
            )

        return {
            "metadata": {
                "risk_ip_hash": ip_hash,
                "risk_ua_hash": ua_hash,
                "risk_phone_hash": phone_hash,
                "risk_user_hash": user_hash,
                "risk_email_hash": email_hash,
                "risk_amount": f"{safe_amount:.2f}",
                "risk_guard": "yeslek_v1",
            }
        }

    # ---------------------------
    # Stripe failed payment tracking
    # ---------------------------
    @classmethod
    def record_failed_payment(
        cls,
        *,
        metadata: Dict[str, Any],
    ) -> None:

        cls._ensure_table()

        now = int(time.time())

        cls._cleanup(now)

        risk_ip_hash = str(
            metadata.get("risk_ip_hash") or ""
        ).strip()

        risk_phone_hash = str(
            metadata.get("risk_phone_hash") or ""
        ).strip()

        risk_user_hash = str(
            metadata.get("risk_user_hash") or ""
        ).strip()
        risk_email_hash = str(
            metadata.get("risk_email_hash") or ""
        ).strip()
        keys = []

        if risk_ip_hash:
            keys.append(f"failed:ip:{risk_ip_hash}")

        if risk_phone_hash:
            keys.append(f"failed:phone:{risk_phone_hash}")

        if risk_user_hash:
            keys.append(f"failed:user:{risk_user_hash}")
        if risk_email_hash:
            keys.append(f"failed:email:{risk_email_hash}")

        for event_key in keys:
            try:
                cls._register_and_check(
                    event_key=event_key,
                    event_type="stripe_failed",
                    limit=50,
                    window_seconds=8640,
                    block_seconds=86400,
                    now=now,
                )
            except PaymentGuardError:
                continue