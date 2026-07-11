# ---------------------------
# Account routes — FINAL PRO
# ---------------------------

import os
from flask import Blueprint, render_template, session, request, redirect, url_for, current_app
from werkzeug.utils import secure_filename

from services.order.order_service import OrderService
from services.user.user_service import UserService
from services.account.card_service import CardService

account_bp = Blueprint("account", __name__, url_prefix="/account")


# ---------------------------
# About page
# ---------------------------
@account_bp.route("/about")
def about():
    return render_template("account/about.html")


# ---------------------------
# Payment methods page
# ---------------------------
@account_bp.route("/payment-methods")
def card_storage_get():

    user_id = session.get("user_id")

    current_app.logger.info(
        "CARD STORAGE SESSION | user_id=%s",
        user_id,
    )

    if not user_id:

        return redirect(
            url_for("auth.login_get")
        )

    try:

        cards = CardService.get_user_cards(
            str(user_id)
        )

        current_app.logger.info(
            "CARD STORAGE RESULT | user_id=%s | count=%s | cards=%s",
            user_id,
            len(cards),
            cards,
        )

    except Exception as exc:

        current_app.logger.exception(
            "CARD STORAGE ERROR | user_id=%s | error=%s",
            user_id,
            exc,
        )

        cards = []

    return render_template(
        "account/card_storage.html",
        cards=cards,
    )

# ---------------------------
# Profile page
# ---------------------------
@account_bp.route("/profile", methods=["GET", "POST"])
def profile():

    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("auth.login"))

    # =========================
    # SAVE
    # =========================
    if request.method == "POST":

        name = (request.form.get("name") or "").strip()
        birthdate = request.form.get("birthdate") or ""

        # ---- UPDATE USER (DB JSON) ----
        UserService.update(
            user_id=user_id,
            name=name
        )

        # ---- UPDATE SESSION (UI instant) ----
        if name:
            session["user_name"] = name

        if birthdate:
            session["user_birthdate"] = birthdate

        # ---- AVATAR ----
        file = request.files.get("avatar")

        if file and file.filename:

            filename = secure_filename(file.filename)

            upload_folder = os.path.join(
                current_app.static_folder,
                "uploads",
                "avatars"
            )

            os.makedirs(upload_folder, exist_ok=True)

            path = os.path.join(upload_folder, filename)
            file.save(path)

            avatar_url = f"/static/uploads/avatars/{filename}"

            session["user_avatar"] = avatar_url

            # Optionnel : sauvegarder aussi en user
            UserService.update_avatar(user_id, avatar_url)

        return redirect(url_for("account.profile"))

# =========================
# READ (IMPORTANT)
# =========================
    user_data = UserService.get_by_id(user_id)

    user = {
    "name": getattr(user_data, "name", None) or session.get("user_name", "Utilisateur"),
    "email": getattr(user_data, "email", None) or session.get("user_email", ""),
    "phone": getattr(user_data, "phone", None) or session.get("user_phone", ""),
    "birthdate": getattr(user_data, "birthdate", None) or session.get("user_birthdate", ""),
    "avatar": getattr(user_data, "avatar", None) or session.get("user_avatar"),
}

    return render_template(
        "account/profile.html",
        user=user
    )