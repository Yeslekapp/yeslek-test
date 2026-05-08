import time
import uuid
from decimal import Decimal, InvalidOperation

# ---------------------------
# In-memory store (prod: DB/Redis)
# ---------------------------
_CHECKOUTS: dict[str, dict] = {}

# ---------------------------
# Points (mock)
# ---------------------------
def get_points_balance() -> float:
    # prod: per-user (DB)
    return 0.0


def _to_amount(value: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return Decimal("0.00")


def compute_points_usage(amount: str, use_points: bool) -> tuple[float, str]:
    total = _to_amount(amount)
    if not use_points:
        return 0.0, f"{total:.2f}"

    points = Decimal(str(get_points_balance())).quantize(Decimal("0.01"))
    used = min(points, total)
    final = (total - used).quantize(Decimal("0.01"))
    return float(used), f"{final:.2f}"


# ---------------------------
# Checkout lifecycle
# ---------------------------
def create_checkout(*, phone: str, amount: str, final_amount: str, points_used: float, method: str, save_card: bool) -> dict:
    cid = str(uuid.uuid4())
    now = int(time.time())

    checkout = {
        "id": cid,
        "status": "created",
        "phone": phone or "",
        "amount": str(amount),
        "final_amount": str(final_amount),
        "points_used": float(points_used),
        "method": method,
        "save_card": bool(save_card),
        "order_number": str(int(time.time() * 1000)),
        "reference": str(int(time.time() * 1000000)),
        "created_at": now,
        "paid_at": None,
    }
    _CHECKOUTS[cid] = checkout
    return checkout


def get_checkout(checkout_id: str | None) -> dict | None:
    if not checkout_id:
        return None
    return _CHECKOUTS.get(checkout_id)


def mark_payment_success(checkout_id: str) -> None:
    c = _CHECKOUTS.get(checkout_id)
    if not c:
        return
    c["status"] = "paid"
    c["paid_at"] = int(time.time())