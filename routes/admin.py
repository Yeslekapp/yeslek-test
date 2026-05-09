# ---------------------------
# Admin.py — YESLEK PRO PANEL
# ---------------------------

from functools import wraps
from flask import Blueprint, render_template, redirect, session, url_for, request, Response

import config
from services.admin.admin_service import AdminService
from services.order.history_service import HistoryService
from services.core.utils import mask_phone

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------
# Admin auth helpers
# ---------------------------
def _current_user_email() -> str:
    return (session.get("user_email") or "").strip().lower()


def _is_admin() -> bool:
    email = _current_user_email()

    admin_emails = {
        str(e).strip().lower()
        for e in getattr(config, "ADMIN_EMAILS", [])
        if e
    }

    super_admin_email = (
        str(getattr(config, "SUPER_ADMIN_EMAIL", "") or "")
        .strip()
        .lower()
    )

    is_super = bool(email and email == super_admin_email)
    is_admin = bool(email and (email in admin_emails or is_super))

    session["is_admin"] = is_admin
    session["is_super_admin"] = is_super

    return is_admin


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))

        if not _is_admin():
            return redirect(url_for("recharge.enter_number_get"))

        return view_func(*args, **kwargs)

    return wrapped


# ---------------------------
# Shared context
# ---------------------------
def _shared_context(active: str = "dashboard") -> dict:
    return {
        "active_admin_page": active,
        "history_count": HistoryService.count_all(),
        "is_super_admin": session.get("is_super_admin", False),
        "admin_email": session.get("user_email"),
    }


def _mask_items(items):
    return [
        {
            **item,
            "phone": mask_phone(
                item.get("phone"),
                session.get("is_super_admin", False),
            ),
        }
        for item in items
    ]


# ---------------------------
# Dashboard
# ---------------------------
@admin_bp.get("/")
@admin_required
def dashboard_get():
    dashboard = AdminService.get_dashboard_data()
    stats = AdminService.get_dashboard_stats()

    return render_template(
        "admin/dashboard.html",
        dashboard=dashboard,
        stats=stats,
        recent_recharges=_mask_items(dashboard.get("recent_recharges", [])),
        top_countries=AdminService.get_top_countries(),
        top_operators=AdminService.get_top_operators(),
        system_health=AdminService.get_system_health(),
        fraud_alerts=AdminService.get_fraud_alerts(limit=5),
        **_shared_context("dashboard"),
    )


# ---------------------------
# Users
# ---------------------------
@admin_bp.get("/users")
@admin_required
def users_get():
    query = (request.args.get("q") or "").strip()
    users = AdminService.search_users(query) if query else AdminService.get_users()

    return render_template(
        "admin/users.html",
        users=users,
        users_count=len(users),
        query=query,
        **_shared_context("users"),
    )


# ---------------------------
# User detail
# ---------------------------
@admin_bp.get("/user/<user_id>")
@admin_required
def user_detail_get(user_id):
    if not user_id:
        return redirect(url_for("admin.users_get"))

    data = AdminService.get_user_full_detail(user_id)
    user = data.get("user")

    if not user:
        return redirect(url_for("admin.users_get"))

    return render_template(
        "admin/user_detail.html",
        user=user,
        items=_mask_items(data.get("history", [])),
        total=data.get("total_amount", 0),
        count=data.get("count", 0),
        avg=data.get("avg", 0),
        countries=data.get("countries", []),
        top_country=data.get("top_country"),
        cards=data.get("cards", []),
        risk_score=data.get("risk_score", 0),
        **_shared_context("users"),
    )


# ---------------------------
# Recharges
# ---------------------------
@admin_bp.get("/recharges")
@admin_required
def recharges_get():
    recharges = _mask_items(AdminService.get_recharges())

    return render_template(
        "admin/recharges.html",
        recharges=recharges,
        recharges_count=len(recharges),
        **_shared_context("recharges"),
    )


# ---------------------------
# Transactions
# ---------------------------
@admin_bp.get("/transactions")
@admin_required
def transactions_get():
    query = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()

    transactions = AdminService.get_transactions(query=query, status=status)
    transactions = _mask_items(transactions)

    return render_template(
        "admin/transactions.html",
        transactions=transactions,
        transactions_count=len(transactions),
        query=query,
        status=status,
        **_shared_context("transactions"),
    )


# ---------------------------
# Payments
# ---------------------------
@admin_bp.get("/payments")
@admin_required
def payments_get():
    payments = AdminService.get_payments()

    return render_template(
        "admin/payments.html",
        payments=payments,
        payments_count=len(payments),
        **_shared_context("payments"),
    )


# ---------------------------
# Reloadly
# ---------------------------
@admin_bp.get("/reloadly")
@admin_required
def reloadly_get():
    data = AdminService.get_reloadly_overview()

    return render_template(
        "admin/reloadly.html",
        data=data,
        **_shared_context("reloadly"),
    )


# ---------------------------
# Fraud
# ---------------------------
@admin_bp.get("/fraud")
@admin_required
def fraud_get():
    alerts = AdminService.get_fraud_alerts(limit=50)

    return render_template(
        "admin/fraud.html",
        alerts=alerts,
        alerts_count=len(alerts),
        **_shared_context("fraud"),
    )


# ---------------------------
# Support
# ---------------------------
@admin_bp.get("/support")
@admin_required
def support_get():
    tickets = AdminService.get_support_tickets()

    return render_template(
        "admin/support.html",
        tickets=tickets,
        tickets_count=len(tickets),
        **_shared_context("support"),
    )


# ---------------------------
# Promotions
# ---------------------------
@admin_bp.get("/promotions")
@admin_required
def promotions_get():
    promotions = AdminService.get_promotions()

    return render_template(
        "admin/promotions.html",
        promotions=promotions,
        promotions_count=len(promotions),
        **_shared_context("promotions"),
    )


# ---------------------------
# Analytics
# ---------------------------
@admin_bp.get("/analytics")
@admin_required
def analytics_get():
    analytics = AdminService.get_analytics()

    return render_template(
        "admin/analytics.html",
        analytics=analytics,
        **_shared_context("analytics"),
    )


# ---------------------------
# Settings
# ---------------------------
@admin_bp.get("/settings")
@admin_required
def settings_get():
    settings = AdminService.get_admin_settings()

    return render_template(
        "admin/settings.html",
        settings=settings,
        **_shared_context("settings"),
    )


# ---------------------------
# Logs
# ---------------------------
@admin_bp.get("/logs")
@admin_required
def logs_get():
    logs = AdminService.get_logs()

    return render_template(
        "admin/logs.html",
        logs=logs,
        logs_count=len(logs),
        **_shared_context("logs"),
    )


# ---------------------------
# Export CSV
# ---------------------------
@admin_bp.get("/transactions/export")
@admin_required
def transactions_export_get():
    csv_content = AdminService.export_transactions_csv()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=yeslek_transactions.csv"
        },
    )