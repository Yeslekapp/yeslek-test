# ---------------------------
# services/payment/checkout_service.py
# ---------------------------

from __future__ import annotations

import time
import uuid

from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Optional

# ---------------------------
# In-memory store
# (PROD => PostgreSQL / Redis)
# ---------------------------
_CHECKOUTS: dict[str, dict] = {}

# ---------------------------
# Thread safety
# ---------------------------
_CHECKOUT_LOCK = Lock()

# ---------------------------
# Points (mock)
# ---------------------------
def get_points_balance() -> float:
    # TODO:
    # récupérer le solde réel depuis DB
    return 0.0


# ---------------------------
# Safe decimal helper
# ---------------------------
def _to_amount(value: str) -> Decimal:

    try:

        return Decimal(
            str(value)
        ).quantize(
            Decimal("0.01")
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):

        return Decimal("0.00")


# ---------------------------
# Compute points usage
# ---------------------------
def compute_points_usage(
    amount: str,
    use_points: bool,
) -> tuple[float, str]:

    total = _to_amount(amount)

    if not use_points:

        return (
            0.0,
            f"{total:.2f}",
        )

    points = Decimal(
        str(get_points_balance())
    ).quantize(
        Decimal("0.01")
    )

    used = min(
        points,
        total,
    )

    final = (
        total - used
    ).quantize(
        Decimal("0.01")
    )

    return (
        float(used),
        f"{final:.2f}",
    )


# ---------------------------
# Create checkout
# ---------------------------
def create_checkout(
    *,
    phone: str,
    amount: str,
    final_amount: str,
    points_used: float,
    method: str,
    save_card: bool,
) -> dict:

    cid = str(uuid.uuid4())

    now = int(time.time())

    checkout = {

        # ---------------------------
        # IDs
        # ---------------------------
        "id": cid,

        # ---------------------------
        # Status
        # ---------------------------
        # created
        # processing
        # paid
        # failed
        # refunded
        # ---------------------------
        "status": "created",

        # ---------------------------
        # User
        # ---------------------------
        "phone": phone or "",

        # ---------------------------
        # Amounts
        # ---------------------------
        "amount": str(amount),
        "final_amount": str(final_amount),
        "points_used": float(points_used),

        # ---------------------------
        # Payment
        # ---------------------------
        "method": method,
        "save_card": bool(save_card),

        # ---------------------------
        # References
        # ---------------------------
        "order_number": (
            uuid.uuid4()
            .hex[:12]
            .upper()
        ),

        "reference": (
            uuid.uuid4()
            .hex[:16]
            .upper()
        ),

        # ---------------------------
        # Dates
        # ---------------------------
        "created_at": now,
        "updated_at": now,
        "paid_at": None,
    }

    # ---------------------------
    # Thread-safe storage
    # ---------------------------
    with _CHECKOUT_LOCK:

        _CHECKOUTS[cid] = checkout

    return checkout


# ---------------------------
# Get checkout
# ---------------------------
def get_checkout(
    checkout_id: Optional[str]
) -> Optional[dict]:

    if not checkout_id:

        return None

    with _CHECKOUT_LOCK:

        return _CHECKOUTS.get(
            checkout_id
        )


# ---------------------------
# Mark processing
# ---------------------------
def mark_checkout_processing(
    checkout_id: str
) -> None:

    with _CHECKOUT_LOCK:

        checkout = _CHECKOUTS.get(
            checkout_id
        )

        if not checkout:

            return

        checkout["status"] = "processing"

        checkout["updated_at"] = int(
            time.time()
        )


# ---------------------------
# Mark payment success
# ---------------------------
def mark_payment_success(
    checkout_id: str
) -> None:

    with _CHECKOUT_LOCK:

        checkout = _CHECKOUTS.get(
            checkout_id
        )

        if not checkout:

            return

        now = int(time.time())

        checkout["status"] = "paid"

        checkout["paid_at"] = now

        checkout["updated_at"] = now


# ---------------------------
# Mark payment failed
# ---------------------------
def mark_payment_failed(
    checkout_id: str
) -> None:

    with _CHECKOUT_LOCK:

        checkout = _CHECKOUTS.get(
            checkout_id
        )

        if not checkout:

            return

        checkout["status"] = "failed"

        checkout["updated_at"] = int(
            time.time()
        )


# ---------------------------
# Mark refunded
# ---------------------------
def mark_payment_refunded(
    checkout_id: str
) -> None:

    with _CHECKOUT_LOCK:

        checkout = _CHECKOUTS.get(
            checkout_id
        )

        if not checkout:

            return

        checkout["status"] = "refunded"

        checkout["updated_at"] = int(
            time.time()
        )