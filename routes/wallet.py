# ---------------------------
# Wallet routes (FINAL SEO SAFE)
# ---------------------------

from flask import Blueprint, render_template, session, url_for
from services.user.user_service import UserService

wallet_bp = Blueprint("wallet", __name__, url_prefix="/wallet")


@wallet_bp.get("/")
def wallet_home():

    user_id = session.get("user_id")

    balance = UserService.get_balance(user_id)

    default_amount = 5

    share_link = url_for(
        "payment.card_get",
        amount=default_amount,
        _external=True
    )

    return render_template(
        "wallet/index.html",
        balance=balance,
        default_amount=default_amount,
        share_link=share_link,

        # ---------------------------
        # SEO (IMPORTANT)
        # ---------------------------
        meta_robots="noindex,follow",
        seo_title="Yeslek - Wallet",
        seo_description="Gérez votre solde Yeslek en toute sécurité."
    )