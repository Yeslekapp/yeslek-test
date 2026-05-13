from flask import Blueprint, render_template

seo_bp = Blueprint("seo", __name__)

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

        seo_title=t(f"seoCountries.{country}Title"),

        seo_description=t(
            f"seoCountries.{country}Description"
        ),
    )