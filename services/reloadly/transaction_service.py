# ---------------------------
# Feature: Reloadly Transaction Service
# ---------------------------

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from services.reloadly.airtime_service import get_topup_status, send_topup
from services.reloadly.data_service import send_data_topup


# ---------------------------
# Exceptions
# ---------------------------

class TransactionServiceError(Exception):
    pass


class DuplicateTransactionError(TransactionServiceError):
    pass


class InvalidTransactionInputError(TransactionServiceError):
    pass


class PaymentReferenceMissingError(TransactionServiceError):
    pass


# ---------------------------
# Result model
# ---------------------------

@dataclass
class TransactionResult:
    ok: bool
    status: str
    transaction_id: Optional[int] = None
    custom_identifier: Optional[str] = None
    is_duplicate: bool = False
    message: str = ""
    raw: Optional[Dict[str, Any]] = None


# ---------------------------
# In-memory store fallback
# ---------------------------

_MEM_STORE: Dict[str, Dict[str, Any]] = {}
_MEM_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    with _GLOBAL_LOCK:
        if key not in _MEM_LOCKS:
            _MEM_LOCKS[key] = threading.Lock()
        return _MEM_LOCKS[key]


# ---------------------------
# Helpers
# ---------------------------

def build_transaction_reference(
    *,
    payment_reference: str,
    phone: str,
    amount: float | None = None,
    plan_id: int | None = None,
    operator_id: int | None = None,
    country_iso: str | None = None,
) -> str:
    payment_reference = str(payment_reference or "").strip()
    phone = str(phone or "").strip()
    country_iso = str(country_iso or "").strip().upper()

    if not payment_reference:
        raise PaymentReferenceMissingError("payment_reference manquant")

    if not phone:
        raise InvalidTransactionInputError("phone manquant")

    raw = "|".join(
        [
            payment_reference,
            phone,
            str(amount if amount is not None else ""),
            str(plan_id if plan_id is not None else ""),
            str(operator_id if operator_id is not None else ""),
            country_iso,
        ]
    )

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"tkz_tx_{digest[:40]}"


def normalize_reloadly_status(status: str | None) -> str:
    value = str(status or "").strip().upper()

    if value in {"SUCCESS", "SUCCESSFUL"}:
        return "SUCCESS"
    if value in {"PROCESSING", "PENDING"}:
        return "PROCESSING"
    if value == "REFUNDED":
        return "REFUNDED"
    if value == "FAILED":
        return "FAILED"

    return "UNKNOWN"


def _timestamp() -> int:
    return int(time.time())


def _mem_find(reference: str) -> Optional[Dict[str, Any]]:
    item = _MEM_STORE.get(reference)
    return dict(item) if item else None


def _mem_create_pending(payload: Dict[str, Any]) -> None:
    _MEM_STORE[payload["reference"]] = dict(payload)


def _mem_mark_processing(reference: str, payload: Optional[Dict[str, Any]] = None) -> None:
    item = dict(_MEM_STORE.get(reference, {"reference": reference}))
    item["status"] = "PROCESSING"
    item["updated_at"] = _timestamp()
    if payload:
        item.update(payload)
    _MEM_STORE[reference] = item


def _mem_mark_success(reference: str, payload: Optional[Dict[str, Any]] = None) -> None:
    item = dict(_MEM_STORE.get(reference, {"reference": reference}))
    item["status"] = "SUCCESS"
    item["updated_at"] = _timestamp()
    if payload:
        item.update(payload)
    _MEM_STORE[reference] = item


def _mem_mark_failed(reference: str, payload: Optional[Dict[str, Any]] = None) -> None:
    item = dict(_MEM_STORE.get(reference, {"reference": reference}))
    item["status"] = "FAILED"
    item["updated_at"] = _timestamp()
    if payload:
        item.update(payload)
    _MEM_STORE[reference] = item


def _validate_inputs(
    *,
    phone: str,
    country_iso: str,
    amount: float | None,
    plan_id: int | None,
) -> None:
    if not phone:
        raise InvalidTransactionInputError("phone manquant")

    if not country_iso:
        raise InvalidTransactionInputError("country_iso manquant")

    if plan_id is not None:
        try:
            plan_id = int(plan_id)
        except Exception as exc:
            raise InvalidTransactionInputError("plan_id invalide") from exc

        if plan_id <= 0:
            raise InvalidTransactionInputError("plan_id invalide")
        return

    if amount is None:
        raise InvalidTransactionInputError("amount manquant")

    try:
        amount = float(amount)
    except Exception as exc:
        raise InvalidTransactionInputError("amount invalide") from exc

    if amount <= 0:
        raise InvalidTransactionInputError("amount doit être > 0")


def _build_store_payload(
    *,
    reference: str,
    phone: str,
    country_iso: str,
    amount: float | None,
    plan_id: int | None,
    operator_id: int | None,
    user_id: Any | None,
    metadata: Optional[Dict[str, Any]],
    status: str,
    reloadly_transaction_id: int | None = None,
    raw: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "reference": reference,
        "status": status,
        "phone": phone,
        "country_iso": country_iso,
        "amount": amount,
        "plan_id": plan_id,
        "operator_id": operator_id,
        "user_id": user_id,
        "metadata": metadata or {},
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }

    if reloadly_transaction_id is not None:
        payload["reloadly_transaction_id"] = reloadly_transaction_id

    if raw is not None:
        payload["raw"] = raw

    return payload


def _db_find_by_reference(reference: str):
    from db.database import SessionLocal
    from db.models.transaction import Transaction

    db = SessionLocal()
    try:
        row = db.query(Transaction).filter(Transaction.reference == reference).first()
        if not row:
            return None

        return {
            "id": row.id,
            "reference": row.reference,
            "user_id": row.user_id,
            "phone": row.phone,
            "country_iso": row.country_iso,
            "amount": row.amount,
            "plan_id": row.plan_id,
            "operator_id": row.operator_id,
            "status": normalize_reloadly_status(getattr(row, "status", None)),
            "reloadly_transaction_id": getattr(row, "reloadly_transaction_id", None),
        }
    finally:
        db.close()


def _db_create_or_get_processing(
    *,
    reference: str,
    user_id: Any | None,
    phone: str,
    country_iso: str,
    amount: float | None,
    plan_id: int | None,
    operator_id: int | None,
):
    from db.database import SessionLocal
    from db.models.transaction import Transaction

    db = SessionLocal()
    try:
        existing = db.query(Transaction).filter(Transaction.reference == reference).first()
        if existing:
            return {
                "created": False,
                "row_id": existing.id,
                "status": normalize_reloadly_status(getattr(existing, "status", None)),
                "reloadly_transaction_id": getattr(existing, "reloadly_transaction_id", None),
            }

        tx = Transaction(
            user_id=user_id,
            reference=reference,
            phone=phone,
            country_iso=country_iso,
            amount=float(amount) if amount is not None else None,
            plan_id=int(plan_id) if plan_id is not None else None,
            operator_id=int(operator_id) if operator_id is not None else None,
            status="PROCESSING",
        )

        db.add(tx)
        db.commit()
        db.refresh(tx)

        return {
            "created": True,
            "row_id": tx.id,
            "status": "PROCESSING",
            "reloadly_transaction_id": getattr(tx, "reloadly_transaction_id", None),
        }
    finally:
        db.close()


def _db_update_status(
    *,
    reference: str,
    status: str,
    reloadly_transaction_id: int | None = None,
):
    from db.database import SessionLocal
    from db.models.transaction import Transaction

    db = SessionLocal()
    try:
        tx = db.query(Transaction).filter(Transaction.reference == reference).first()
        if not tx:
            return

        tx.status = status

        if reloadly_transaction_id is not None and hasattr(tx, "reloadly_transaction_id"):
            tx.reloadly_transaction_id = reloadly_transaction_id

        db.commit()
    finally:
        db.close()


# ---------------------------
# Execute recharge (FINAL YESLEK STABLE FIXED)
# ---------------------------

def process_recharge(
    *,
    payment_reference: str,
    phone: str,
    country_iso: str,
    amount: float | None = None,
    plan_id: int | None = None,
    operator_id: int | None = None,
    user_id: Any | None = None,
    metadata: Optional[Dict[str, Any]] = None,
    repo_find: Callable[[str], Optional[Dict[str, Any]]] = _mem_find,
    repo_create_pending: Callable[[Dict[str, Any]], None] = _mem_create_pending,
    repo_mark_processing: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_processing,
    repo_mark_success: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_success,
    repo_mark_failed: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_failed,
) -> TransactionResult:

    _validate_inputs(
        phone=phone,
        country_iso=country_iso,
        amount=amount,
        plan_id=plan_id,
    )

    reference = build_transaction_reference(
        payment_reference=payment_reference,
        phone=phone,
        amount=amount,
        plan_id=plan_id,
        operator_id=operator_id,
        country_iso=country_iso,
    )

    lock = _get_lock(reference)

    with lock:

        existing = _db_find_by_reference(reference) or repo_find(reference)

        if existing:
            status = normalize_reloadly_status(existing.get("status"))

            return TransactionResult(
                ok=(status == "SUCCESS"),
                status=status,
                transaction_id=existing.get("reloadly_transaction_id"),
                custom_identifier=reference,
                is_duplicate=True,
                message="Transaction déjà traitée",
                raw=existing,
            )

        db_result = _db_create_or_get_processing(
            reference=reference,
            user_id=user_id,
            phone=phone,
            country_iso=country_iso,
            amount=amount,
            plan_id=plan_id,
            operator_id=operator_id,
        )

        if not db_result["created"]:
            status = normalize_reloadly_status(db_result.get("status"))

            return TransactionResult(
                ok=(status == "SUCCESS"),
                status=status,
                transaction_id=db_result.get("reloadly_transaction_id"),
                custom_identifier=reference,
                is_duplicate=True,
                message="Transaction déjà enregistrée",
                raw=db_result,
            )

        repo_create_pending({
            "reference": reference,
            "status": "PENDING",
        })

        repo_mark_processing(reference, {"metadata": metadata or {}})

        try:

            # ---------------------------
            # 🔥 CORE FIX (DATA vs AIRTIME)
            # ---------------------------
            if plan_id is not None:
                if not operator_id:
                    raise TransactionServiceError("operator_id requis pour DATA")

                raw_result = send_data_topup(
                    phone=phone,
                    plan_id=int(plan_id),
                    country_iso=country_iso,
                    operator_id=int(operator_id),
                    amount=None,  # 🔥 CRITICAL FIX  
                    custom_identifier=reference,
                )
                print("🔥 RELOADLY DATA RESULT:", raw_result)

            else:
                if amount is None:
                    raise TransactionServiceError("amount requis pour airtime")

                raw_result = send_topup(
                    phone=phone,
                    amount=float(amount),
                    country_iso=country_iso,
                    custom_identifier=reference,
                )

            reloadly_transaction_id = raw_result.get("transaction_id")
            status = normalize_reloadly_status(raw_result.get("status"))

            if status == "UNKNOWN":
                status = "PROCESSING"

            _db_update_status(
                reference=reference,
                status=status,
                reloadly_transaction_id=reloadly_transaction_id,
            )

            payload = {
                "status": status,
                "reloadly_transaction_id": reloadly_transaction_id,
                "raw": raw_result,
            }

            if status == "SUCCESS":
                repo_mark_success(reference, payload)
            elif status == "PROCESSING":
                repo_mark_processing(reference, payload)
            else:
                repo_mark_failed(reference, payload)

            return TransactionResult(
                ok=(status == "SUCCESS"),
                status=status,
                transaction_id=reloadly_transaction_id,
                custom_identifier=reference,
                raw=raw_result,
            )

        except Exception as exc:

            _db_update_status(
                reference=reference,
                status="FAILED",
            )

            repo_mark_failed(reference, {
                "status": "FAILED",
                "error": str(exc),
            })

            raise TransactionServiceError(str(exc)) from exc


# ---------------------------
# Refresh status
# ---------------------------

def refresh_transaction_status(
    *,
    reference: str,
    transaction_id: int | None,
    repo_find: Callable[[str], Optional[Dict[str, Any]]] = _mem_find,
    repo_mark_success: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_success,
    repo_mark_failed: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_failed,
    repo_mark_processing: Callable[[str, Optional[Dict[str, Any]]], None] = _mem_mark_processing,
) -> TransactionResult:
    if not reference:
        raise InvalidTransactionInputError("reference manquante")

    current = repo_find(reference) or _db_find_by_reference(reference)

    if not current and not transaction_id:
        raise InvalidTransactionInputError("transaction introuvable")

    if not transaction_id and current:
        transaction_id = current.get("reloadly_transaction_id")

    if not transaction_id:
        return TransactionResult(
            ok=False,
            status="UNKNOWN",
            custom_identifier=reference,
            message="Aucun transaction_id Reloadly disponible",
            raw=current,
        )

    raw = get_topup_status(transaction_id)
    status = normalize_reloadly_status(raw.get("status"))

    payload = {
        "status": status,
        "reloadly_transaction_id": transaction_id,
        "reloadly_status_raw": raw,
        "updated_at": _timestamp(),
    }

    _db_update_status(
        reference=reference,
        status=status,
        reloadly_transaction_id=transaction_id,
    )

    if status == "SUCCESS":
        repo_mark_success(reference, payload)
    elif status in {"FAILED", "REFUNDED"}:
        repo_mark_failed(reference, payload)
    else:
        repo_mark_processing(reference, payload)

    return TransactionResult(
        ok=(status == "SUCCESS"),
        status=status,
        transaction_id=transaction_id,
        custom_identifier=reference,
        message="Statut synchronisé",
        raw=raw,
    )


# ---------------------------
# Public helper
# ---------------------------

def get_existing_transaction(
    reference: str,
    repo_find: Callable[[str], Optional[Dict[str, Any]]] = _mem_find,
) -> Optional[Dict[str, Any]]:
    if not reference:
        return None

    return repo_find(reference) or _db_find_by_reference(reference)