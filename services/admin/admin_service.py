# ---------------------------
# Admin Service (FINAL PRO CLEAN)
# ---------------------------

from __future__ import annotations

import hashlib
from datetime import datetime

from flask import session

from services.order.history_service import HistoryService
from services.user.user_service import UserService
from services.order.order_service import OrderService
from services.core.utils import mask_phone




class AdminService:
    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            return float(value)
        except:
            return default

    @staticmethod
    def _parse_date(value):
        if not value:
            return None

        formats = [
            "%d/%m/%Y • %H:%M",
            "%d/%m/%Y %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]

        for f in formats:
            try:
                return datetime.strptime(str(value), f)
            except:
                continue

        return None
    # ---------------------------
    # Convert DB -> dict
    # ---------------------------
    @staticmethod
    def _history_items():

        records = HistoryService.get_all() or []

        items = []

        for t in records:
            items.append({
                "user_id": t.user_id,
                "phone": t.phone,
                "amount": float(t.amount or 0),
                "date": t.created_at.strftime("%d/%m/%Y • %H:%M") if t.created_at else None,
                "country": t.country_iso,
            })

        for i in items:
            i["_sort_date"] = AdminService._parse_date(i.get("date"))

        items.sort(
            key=lambda x: x["_sort_date"] or datetime.min,
            reverse=True
        )

        return items

    @staticmethod
    def _users_map():
     users = UserService.get_all() or []
     return {u["user_id"]: u for u in users if u.get("user_id")}

    @staticmethod
    def _transaction_reference(phone, amount, date):
        raw = f"{phone}|{amount:.2f}|{date}"
        digest = hashlib.sha1(raw.encode()).hexdigest()[:12].upper()
        return f"TZ-{digest}"

    # ---------------------------
    # Dashboard
    # ---------------------------
    @staticmethod
    def get_dashboard_data():

        items = AdminService._history_items()

        total = sum(AdminService._safe_float(i["amount"]) for i in items)

        return {
            "total_amount": round(total, 2),
            "total_recharges": len(items),
            "unique_customers": len(set(i.get("user_id") for i in items)),
            "average_amount": round(total / len(items), 2) if items else 0,
            "recent_recharges": items[:6],
        }

    @staticmethod
    def get_dashboard_stats():

        items = AdminService._history_items()

        total = 0
        users = {}

        for i in items:
            amount = AdminService._safe_float(i["amount"])
            phone = i.get("phone") or "—"

            total += amount
            users[phone] = users.get(phone, 0) + amount

        top_user = None
        if users:
            top = max(users, key=users.get)
            top_user = {
                "phone": top,
                "amount": round(users[top], 2)
            }

        return {
            "total_revenue": round(total, 2),
            "total_recharges": len(items),
            "total_users": len(users),
            "top_user": top_user,
        }

    # ---------------------------
    # USERS
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

            if key not in grouped:
                grouped[key] = {
                    "user_id": user_id,
                    "raw_phone": raw_phone,
                    "phone": mask_phone(
                        raw_phone,
                        session.get("is_super_admin", False)
                    ),
                    "email": user.get("email"),
                    "name": user.get("name"),
                    "country": item.get("country"),
                    "recharge_count": 0,
                    "total_amount": 0.0,
                    "last_date": item.get("date"),
                }

            grouped[key]["recharge_count"] += 1
            grouped[key]["total_amount"] += AdminService._safe_float(
                item.get("amount")
            )

        users = list(grouped.values())

        # enrichissement
        for u in users:
            total = u["total_amount"]
            count = u["recharge_count"]

            u["total_amount"] = round(total, 2)
            u["avg_amount"] = round(total / count, 2) if count else 0

            if total >= 200:
                u["tier"] = "vip"
            elif total >= 50:
                u["tier"] = "active"
            else:
                u["tier"] = "new"

        users.sort(
            key=lambda x: (
                AdminService._parse_date(x["last_date"]) or datetime.min,
                x["total_amount"],
            ),
            reverse=True,
        )

        return users

    # ---------------------------
    # SEARCH
    # ---------------------------
    @staticmethod
    def search_users(query):

        users = AdminService.get_users()

        if not query:
            return users

        q = query.strip().lower()

        return [
            u for u in users
            if q in (u.get("raw_phone") or "").lower()
            or q in (u.get("email") or "").lower()
            or q in (u.get("name") or "").lower()
        ]

    # ---------------------------
    # USER DETAIL
    # ---------------------------
    @staticmethod
    def get_user_full_detail(user_id):

        history = HistoryService.get_all()
        users = UserService.get_all()
        cards = OrderService.get_saved_cards()

        user = next((u for u in users if u["user_id"] == user_id), None)

        user_history = [
        h for h in history if h.user_id == user_id
      ]

        total = sum(
            AdminService._safe_float(h.amount)
            for h in user_history
        )

        count = len(user_history)
        avg = round(total / count, 2) if count else 0

        countries = [
         h.country
        for h in user_history if h.country
     ]

        country_stats = {}
        for c in countries:
            country_stats[c] = country_stats.get(c, 0) + 1

        top_country = (
            max(country_stats, key=country_stats.get)
            if country_stats else None
        )

        return {
            "user": user,
            "history": user_history,
            "total_amount": round(total, 2),
            "count": count,
            "avg": avg,
            "countries": list(set(countries)),
            "top_country": top_country,
            "cards": cards,
        }

    # ---------------------------
    # RECHARGES
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
                "email": user.get("email"),
                "name": user.get("name"),
                "status": "success",
            })

        return result

    # ---------------------------
    # TRANSACTIONS
    # ---------------------------
    @staticmethod
    def get_transactions():

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
                "email": user.get("email"),
                "name": user.get("name"),
                "status": "success",
                "reference": AdminService._transaction_reference(
                    item.get("phone"),
                    AdminService._safe_float(item.get("amount")),
                    item.get("date"),
                ),
            })

        return result