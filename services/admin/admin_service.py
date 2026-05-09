# ---------------------------
# Admin Service — YESLEK PRO PANEL
# ---------------------------

from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from typing import Any

from flask import session

from services.order.history_service import HistoryService
from services.user.user_service import UserService
from services.order.order_service import OrderService
from services.core.utils import mask_phone


class AdminService:
    # ---------------------------
    # Safe helpers
    # ---------------------------
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_str(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _get_attr(obj: Any, name: str, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _parse_date(value: Any):
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        formats = [
            "%d/%m/%Y • %H:%M",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for date_format in formats:
            try:
                return datetime.strptime(str(value), date_format)
            except (TypeError, ValueError):
                continue

        return None

    @staticmethod
    def _country_from_history(item: Any):
        return (
            AdminService._get_attr(item, "country_iso")
            or AdminService._get_attr(item, "country")
            or AdminService._get_attr(item, "country_name")
            or "—"
        )

    @staticmethod
    def _operator_from_history(item: Any):
        return (
            AdminService._get_attr(item, "operator_name")
            or AdminService._get_attr(item, "operator")
            or "Mobile Top-up"
        )

    # ---------------------------
    # Core data
    # ---------------------------
    @staticmethod
    def _history_items():
        records = HistoryService.get_all() or []
        items = []

        for record in records:
            created_at = AdminService._get_attr(record, "created_at")
            amount = AdminService._safe_float(AdminService._get_attr(record, "amount"))

            item = {
                "user_id": AdminService._get_attr(record, "user_id"),
                "phone": AdminService._get_attr(record, "phone"),
                "amount": round(amount, 2),
                "date": created_at.strftime("%d/%m/%Y • %H:%M") if created_at else None,
                "country": AdminService._country_from_history(record),
                "operator": AdminService._operator_from_history(record),
                "status": AdminService._get_attr(record, "status", "success") or "success",
                "_sort_date": created_at if isinstance(created_at, datetime) else None,
            }

            if not item["_sort_date"]:
                item["_sort_date"] = AdminService._parse_date(item.get("date"))

            items.append(item)

        items.sort(
            key=lambda x: x.get("_sort_date") or datetime.min,
            reverse=True,
        )

        return items

    @staticmethod
    def _users_map():
        users = UserService.get_all() or []

        return {
            AdminService._get_attr(user, "user_id"): user
            for user in users
            if AdminService._get_attr(user, "user_id")
        }

    @staticmethod
    def _transaction_reference(phone, amount, date):
        raw = f"{phone or 'unknown'}|{amount:.2f}|{date or 'no-date'}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:14].upper()
        return f"YS-{digest}"

    @staticmethod
    def _user_saved_cards(user_id):
        cards = OrderService.get_saved_cards() or []

        filtered = []
        for card in cards:
            card_user_id = AdminService._get_attr(card, "user_id")
            if not card_user_id or card_user_id == user_id:
                filtered.append(card)

        return filtered

    # ---------------------------
    # Dashboard
    # ---------------------------
    @staticmethod
    def get_dashboard_data():
        items = AdminService._history_items()
        total = sum(AdminService._safe_float(i.get("amount")) for i in items)

        unique_customers = {
            i.get("user_id") or i.get("phone")
            for i in items
            if i.get("user_id") or i.get("phone")
        }

        today = datetime.utcnow().date()
        today_items = [
            i for i in items
            if i.get("_sort_date") and i["_sort_date"].date() == today
        ]

        failed_items = [
            i for i in items
            if str(i.get("status")).lower() in {"failed", "error", "declined"}
        ]

        success_count = len(items) - len(failed_items)
        success_rate = round((success_count / len(items)) * 100, 1) if items else 0

        return {
            "total_amount": round(total, 2),
            "total_recharges": len(items),
            "today_transactions": len(today_items),
            "failed_transactions": len(failed_items),
            "success_rate": success_rate,
            "unique_customers": len(unique_customers),
            "average_amount": round(total / len(items), 2) if items else 0,
            "recent_recharges": items[:8],
        }

    @staticmethod
    def get_dashboard_stats():
        items = AdminService._history_items()

        total = 0.0
        users = {}

        for item in items:
            amount = AdminService._safe_float(item.get("amount"))
            user_key = item.get("user_id") or item.get("phone") or "unknown"

            total += amount
            users[user_key] = users.get(user_key, 0.0) + amount

        top_user = None
        if users:
            top_key = max(users, key=users.get)
            top_item = next(
                (
                    i for i in items
                    if (i.get("user_id") or i.get("phone") or "unknown") == top_key
                ),
                {},
            )

            top_user = {
                "phone": mask_phone(
                    top_item.get("phone"),
                    session.get("is_super_admin", False),
                ),
                "amount": round(users[top_key], 2),
            }

        dashboard = AdminService.get_dashboard_data()

        return {
            "total_revenue": round(total, 2),
            "total_recharges": len(items),
            "today_transactions": dashboard.get("today_transactions", 0),
            "success_rate": dashboard.get("success_rate", 0),
            "failed_transactions": dashboard.get("failed_transactions", 0),
            "total_users": len(users),
            "stripe_revenue": round(total, 2),
            "reloadly_balance": 0,
            "top_user": top_user,
        }

    # ---------------------------
    # Users
    # ---------------------------
    @staticmethod
    def get_users():
        items = AdminService._history_items()
        users_map = AdminService._users_map()

        grouped = {}

        for item in items:
            user_id = item.get("user_id")
            user = users_map.get(user_id, {})

            raw_phone = item.get("phone")
            key = user_id or raw_phone

            if not key:
                continue

            if key not in grouped:
                grouped[key] = {
                    "user_id": user_id,
                    "raw_phone": raw_phone,
                    "phone": mask_phone(
                        raw_phone,
                        session.get("is_super_admin", False),
                    ),
                    "email": AdminService._get_attr(user, "email"),
                    "name": AdminService._get_attr(user, "name"),
                    "country": item.get("country"),
                    "recharge_count": 0,
                    "total_amount": 0.0,
                    "last_date": item.get("date"),
                }

            grouped[key]["recharge_count"] += 1
            grouped[key]["total_amount"] += AdminService._safe_float(item.get("amount"))

        users = list(grouped.values())

        for user in users:
            total = AdminService._safe_float(user.get("total_amount"))
            count = int(user.get("recharge_count") or 0)

            user["total_amount"] = round(total, 2)
            user["avg_amount"] = round(total / count, 2) if count else 0

            if total >= 200:
                user["tier"] = "vip"
            elif total >= 50:
                user["tier"] = "active"
            else:
                user["tier"] = "new"

        users.sort(
            key=lambda x: (
                AdminService._parse_date(x.get("last_date")) or datetime.min,
                AdminService._safe_float(x.get("total_amount")),
            ),
            reverse=True,
        )

        return users

    @staticmethod
    def search_users(query):
        users = AdminService.get_users()

        q = AdminService._safe_str(query).lower()
        if not q:
            return users

        return [
            user for user in users
            if q in AdminService._safe_str(user.get("raw_phone")).lower()
            or q in AdminService._safe_str(user.get("phone")).lower()
            or q in AdminService._safe_str(user.get("email")).lower()
            or q in AdminService._safe_str(user.get("name")).lower()
        ]

    # ---------------------------
    # User detail
    # ---------------------------
    @staticmethod
    def get_user_full_detail(user_id):
        history = HistoryService.get_all() or []
        users = UserService.get_all() or []

        user = next(
            (
                u for u in users
                if AdminService._get_attr(u, "user_id") == user_id
            ),
            None,
        )

        user_history_raw = [
            h for h in history
            if AdminService._get_attr(h, "user_id") == user_id
        ]

        user_history = []
        for item in user_history_raw:
            created_at = AdminService._get_attr(item, "created_at")
            amount = AdminService._safe_float(AdminService._get_attr(item, "amount"))

            user_history.append({
                "user_id": AdminService._get_attr(item, "user_id"),
                "phone": AdminService._get_attr(item, "phone"),
                "amount": round(amount, 2),
                "date": created_at.strftime("%d/%m/%Y • %H:%M") if created_at else None,
                "country": AdminService._country_from_history(item),
                "operator": AdminService._operator_from_history(item),
                "_sort_date": created_at if isinstance(created_at, datetime) else None,
            })

        user_history.sort(
            key=lambda x: x.get("_sort_date") or datetime.min,
            reverse=True,
        )

        total = sum(AdminService._safe_float(h.get("amount")) for h in user_history)
        count = len(user_history)
        avg = round(total / count, 2) if count else 0

        countries = [
            h.get("country")
            for h in user_history
            if h.get("country") and h.get("country") != "—"
        ]

        country_stats = {}
        for country in countries:
            country_stats[country] = country_stats.get(country, 0) + 1

        top_country = max(country_stats, key=country_stats.get) if country_stats else None
        risk_score = min(100, max(0, count * 3))

        return {
            "user": user,
            "history": user_history,
            "total_amount": round(total, 2),
            "count": count,
            "avg": avg,
            "countries": sorted(set(countries)),
            "top_country": top_country,
            "cards": AdminService._user_saved_cards(user_id),
            "risk_score": risk_score,
        }

    # ---------------------------
    # Recharges
    # ---------------------------
    @staticmethod
    def get_recharges():
        items = AdminService._history_items()
        users_map = AdminService._users_map()

        result = []

        for item in items:
            user = users_map.get(item.get("user_id"), {})

            result.append({
                "user_id": item.get("user_id"),
                "phone": item.get("phone"),
                "amount": item.get("amount"),
                "date": item.get("date"),
                "country": item.get("country"),
                "operator": item.get("operator"),
                "email": AdminService._get_attr(user, "email"),
                "name": AdminService._get_attr(user, "name"),
                "status": item.get("status", "success"),
            })

        return result

    # ---------------------------
    # Transactions
    # ---------------------------
    @staticmethod
    def get_transactions(query: str = "", status: str = ""):
        items = AdminService._history_items()
        users_map = AdminService._users_map()

        result = []

        for item in items:
            amount = AdminService._safe_float(item.get("amount"))
            user = users_map.get(item.get("user_id"), {})

            row = {
                "user_id": item.get("user_id"),
                "phone": item.get("phone"),
                "amount": amount,
                "date": item.get("date"),
                "country": item.get("country"),
                "operator": item.get("operator"),
                "email": AdminService._get_attr(user, "email"),
                "name": AdminService._get_attr(user, "name"),
                "status": item.get("status", "success"),
                "provider": "Reloadly",
                "payment_provider": "Stripe",
                "reference": AdminService._transaction_reference(
                    item.get("phone"),
                    amount,
                    item.get("date"),
                ),
            }

            result.append(row)

        q = AdminService._safe_str(query).lower()
        if q:
            result = [
                r for r in result
                if q in AdminService._safe_str(r.get("reference")).lower()
                or q in AdminService._safe_str(r.get("phone")).lower()
                or q in AdminService._safe_str(r.get("email")).lower()
                or q in AdminService._safe_str(r.get("country")).lower()
                or q in AdminService._safe_str(r.get("operator")).lower()
            ]

        status_q = AdminService._safe_str(status).lower()
        if status_q:
            result = [
                r for r in result
                if AdminService._safe_str(r.get("status")).lower() == status_q
            ]

        return result

    # ---------------------------
    # New admin modules
    # ---------------------------
    @staticmethod
    def get_payments():
        transactions = AdminService.get_transactions()

        return [
            {
                **tx,
                "stripe_id": f"pi_{tx['reference'].replace('YS-', '').lower()}",
                "method": "card",
                "captured": True,
                "refunded": False,
            }
            for tx in transactions
        ]

    @staticmethod
    def get_reloadly_overview():
        return {
            "balance": 0,
            "last_sync": "—",
            "countries": AdminService.get_top_countries(),
            "operators": AdminService.get_top_operators(),
            "recent": AdminService.get_recharges()[:8],
        }

    @staticmethod
    def get_top_countries(limit: int = 6):
        stats = {}

        for item in AdminService._history_items():
            country = item.get("country") or "—"
            stats[country] = stats.get(country, 0) + 1

        rows = [
            {"name": name, "count": count}
            for name, count in stats.items()
            if name != "—"
        ]

        rows.sort(key=lambda x: x["count"], reverse=True)
        return rows[:limit]

    @staticmethod
    def get_top_operators(limit: int = 6):
        stats = {}

        for item in AdminService._history_items():
            operator = item.get("operator") or "Mobile Top-up"
            stats[operator] = stats.get(operator, 0) + 1

        rows = [
            {"name": name, "count": count}
            for name, count in stats.items()
        ]

        rows.sort(key=lambda x: x["count"], reverse=True)
        return rows[:limit]

    @staticmethod
    def get_fraud_alerts(limit: int = 20):
        alerts = []
        users = AdminService.get_users()

        for user in users:
            if user.get("recharge_count", 0) >= 5:
                alerts.append({
                    "level": "medium",
                    "title": "Activité élevée",
                    "description": f"{user.get('phone')} a effectué plusieurs recharges.",
                    "date": user.get("last_date") or "—",
                    "score": min(100, int(user.get("recharge_count", 0)) * 12),
                })

        return alerts[:limit]

    @staticmethod
    def get_support_tickets():
        return []

    @staticmethod
    def get_promotions():
        return []

    @staticmethod
    def get_analytics():
        items = AdminService._history_items()
        total = sum(AdminService._safe_float(i.get("amount")) for i in items)

        return {
            "total_revenue": round(total, 2),
            "total_transactions": len(items),
            "average_amount": round(total / len(items), 2) if items else 0,
            "top_countries": AdminService.get_top_countries(),
            "top_operators": AdminService.get_top_operators(),
        }

    @staticmethod
    def get_admin_settings():
        return {
            "security": True,
            "notifications": True,
            "integrations": ["Stripe", "Reloadly", "Telnyx", "Brevo"],
            "appearance": "auto",
        }

    @staticmethod
    def get_logs():
        return [
            {
                "level": "info",
                "source": "admin",
                "message": "Admin panel chargé",
                "date": datetime.utcnow().strftime("%d/%m/%Y • %H:%M"),
            }
        ]

    @staticmethod
    def get_system_health():
        return [
            {"name": "Stripe", "status": "success"},
            {"name": "Reloadly", "status": "success"},
            {"name": "Telnyx", "status": "success"},
            {"name": "Brevo", "status": "success"},
        ]

    @staticmethod
    def export_transactions_csv():
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "reference",
            "phone",
            "amount",
            "status",
            "country",
            "operator",
            "date",
            "provider",
            "payment_provider",
        ])

        for tx in AdminService.get_transactions():
            writer.writerow([
                tx.get("reference"),
                tx.get("phone"),
                tx.get("amount"),
                tx.get("status"),
                tx.get("country"),
                tx.get("operator"),
                tx.get("date"),
                tx.get("provider"),
                tx.get("payment_provider"),
            ])

        return output.getvalue()