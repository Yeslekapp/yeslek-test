# ---------------------------
# OTP Service — in-memory development storage
# ---------------------------

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from threading import RLock

from config import OTP_PEPPER


# ---------------------------
# Internal record
# ---------------------------

@dataclass
class _OtpRecord:
    digest: str
    expires_at: float
    attempts_remaining: int


# ---------------------------
# In-memory storage
# ---------------------------

_memory_store: dict[str, _OtpRecord] = {}
_store_lock = RLock()


# ---------------------------
# OTP Service
# ---------------------------

class OtpService:

    TTL = 300
    MAX_ATTEMPTS = 5

    @staticmethod
    def generate_code(length: int = 6) -> str:
        if length < 4 or length > 8:
            raise ValueError(
                "OTP length must be between 4 and 8"
            )

        return "".join(
            secrets.choice("0123456789")
            for _ in range(length)
        )

    @staticmethod
    def build_key(
        channel: str,
        target: str,
    ) -> str:
        clean_channel = str(
            channel or ""
        ).strip().lower()

        clean_target = str(
            target or ""
        ).strip().lower()

        if not clean_channel or not clean_target:
            raise ValueError(
                "OTP channel and target are required"
            )

        return f"{clean_channel}:{clean_target}"

    @staticmethod
    def _require_pepper() -> str:
        pepper = str(
            OTP_PEPPER or ""
        ).strip()

        if not pepper:
            raise RuntimeError(
                "OTP_PEPPER is not configured"
            )

        return pepper

    @classmethod
    def _digest_code(
        cls,
        key: str,
        code: str,
    ) -> str:
        pepper = cls._require_pepper()

        payload = f"{key}:{code}".encode("utf-8")

        return hmac.new(
            pepper.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def _cleanup_expired_locked(
        cls,
        now: float,
    ) -> None:
        expired_keys = [
            key
            for key, record in _memory_store.items()
            if record.expires_at <= now
        ]

        for key in expired_keys:
            _memory_store.pop(key, None)

    @classmethod
    def store_otp(
        cls,
        channel: str,
        target: str,
        code: str,
    ) -> None:
        clean_code = str(
            code or ""
        ).strip()

        if not clean_code.isdigit():
            raise ValueError(
                "OTP code must contain digits only"
            )

        key = cls.build_key(
            channel,
            target,
        )

        now = time.time()

        record = _OtpRecord(
            digest=cls._digest_code(
                key,
                clean_code,
            ),
            expires_at=now + cls.TTL,
            attempts_remaining=cls.MAX_ATTEMPTS,
        )

        with _store_lock:
            cls._cleanup_expired_locked(now)
            _memory_store[key] = record

    @classmethod
    def verify_otp(
        cls,
        channel: str,
        target: str,
        entered_code: str,
    ) -> bool:
        clean_code = str(
            entered_code or ""
        ).strip()

        if not clean_code.isdigit():
            return False

        key = cls.build_key(
            channel,
            target,
        )

        now = time.time()

        with _store_lock:
            cls._cleanup_expired_locked(now)

            record = _memory_store.get(key)

            if record is None:
                return False

            candidate_digest = cls._digest_code(
                key,
                clean_code,
            )

            if hmac.compare_digest(
                record.digest,
                candidate_digest,
            ):
                _memory_store.pop(key, None)
                return True

            record.attempts_remaining -= 1

            if record.attempts_remaining <= 0:
                _memory_store.pop(key, None)

            return False

    @classmethod
    def delete_otp(
        cls,
        channel: str,
        target: str,
    ) -> None:
        key = cls.build_key(
            channel,
            target,
        )

        with _store_lock:
            _memory_store.pop(key, None)