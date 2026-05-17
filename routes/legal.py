# ---------------------------
# Legal Routes — Privacy / Data Deletion
# ---------------------------

from flask import Blueprint

legal_bp = Blueprint("legal", __name__)


@legal_bp.get("/privacy")
def privacy_policy():
    return """
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <title>Politique de confidentialité - Yeslek</title>
    </head>
    <body>
        <h1>Politique de confidentialité</h1>

        <p>
            Yeslek collecte uniquement les informations nécessaires pour fournir
            ses services de recharge mobile, d’authentification et de paiement.
        </p>

        <h2>Données collectées</h2>
        <p>
            Nous pouvons collecter votre nom, adresse e-mail, numéro de téléphone,
            photo de profil Facebook/Google, historique de recharge et informations
            nécessaires au traitement des paiements.
        </p>

        <h2>Utilisation des données</h2>
        <p>
            Les données sont utilisées pour créer votre compte, sécuriser la connexion,
            traiter les recharges, gérer les paiements et améliorer le service.
        </p>

        <h2>Partage des données</h2>
        <p>
            Nous ne vendons pas vos données. Certaines données peuvent être partagées
            avec nos fournisseurs techniques nécessaires au service, comme Stripe,
            Reloadly, Telnyx ou Brevo.
        </p>

        <h2>Suppression des données</h2>
        <p>
            Vous pouvez demander la suppression de vos données à tout moment via la page :
            <a href="/data-deletion">Suppression des données</a>.
        </p>

        <h2>Contact</h2>
        <p>
            Pour toute question, contactez-nous à : support@yeslek.com
        </p>
    </body>
    </html>
    """


@legal_bp.get("/data-deletion")
def data_deletion():
    return """
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <title>Suppression des données - Yeslek</title>
    </head>
    <body>
        <h1>Suppression des données utilisateur</h1>

        <p>
            Si vous souhaitez supprimer vos données de Yeslek, envoyez une demande à :
        </p>

        <p>
            <strong>support@yeslek.com</strong>
        </p>

        <p>
            Veuillez inclure l’adresse e-mail ou le numéro de téléphone utilisé
            pour votre compte Yeslek.
        </p>

        <p>
            Votre demande sera traitée dans un délai raisonnable.
        </p>
    </body>
    </html>
    """