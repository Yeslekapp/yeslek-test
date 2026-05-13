# ---------------------------
# Feature: SEO Pages
# ---------------------------

from flask import Blueprint, render_template, g

seo_bp = Blueprint("seo", __name__)


# ---------------------------
# Translation helper
# ---------------------------

def t(key: str, default: str = ""):

    cur = g.get("l10n", {})

    for part in key.split("."):

        if not isinstance(cur, dict):
            return default or key

        cur = cur.get(part)

        if cur is None:
            return default or key

    return cur if isinstance(cur, str) else default or key


# ---------------------------
# SEO Countries Pages
# ---------------------------

@seo_bp.get("/recharge-<country>")
def recharge_country(country):

    allowed_countries = {
        "afghanistan",
        "pakistan",
        "inde",
        "cuba",
        "turquie",
        "maroc",
        "algerie",
        "tunisie",
        "bangladesh",
        "senegal",
        "cameroun",
        "nigeria",
    }

    if country not in allowed_countries:
        return render_template("404.html"), 404

    return render_template(
        "seo/country.html",

        country=country,

        canonical_url=f"https://yeslek.com/recharge-{country}",

        seo_title=t(
            f"seoCountries.{country}Title"
        ),

        seo_description=t(
            f"seoCountries.{country}Description"
        ),
    )