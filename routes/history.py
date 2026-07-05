# ---------------------------
# History Routes (FINAL SECURE)
# ---------------------------

from flask import Blueprint, render_template, session, redirect, url_for
from services.auth_guard import login_required
from services.order.history_service import HistoryService

history_bp = Blueprint("history", __name__, url_prefix="/history")


# ---------------------------
# History history
# ---------------------------
@history_bp.get("/")
@login_required
def history_get():

    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("auth.login"))

    # ✅ uniquement les transactions du user
    history_items = HistoryService.get_by_user(user_id)
    history_count = len(history_items)

    return render_template(
        "history/history.html",
        items=history_items,
        history_count=history_count,
    )