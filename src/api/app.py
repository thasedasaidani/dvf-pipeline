"""
Étape 5 — API Flask d'exposition des prix au m² (lecture des tables PostgreSQL).

Lancement local :
    flask --app src.api.app run --port 8000
Exemples :
    http://localhost:8000/prix?commune=Juvisy-sur-Orge
    http://localhost:8000/prix?commune=Juvisy-sur-Orge&type=Appartement&annee=2025
    http://localhost:8000/departements/91
    http://localhost:8000/communes?q=juv
"""

from __future__ import annotations

import logging

import psycopg
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import BadRequest, HTTPException, NotFound

from src.api.db import PostgresRepository

load_dotenv()
log = logging.getLogger("api")

TYPES_VALIDES = {"Appartement", "Maison"}


def create_app(repository=None) -> Flask:
    """Fabrique de l'application. Les tests passent un faux `repository` (sans base)."""
    app = Flask(__name__)
    app.json.ensure_ascii = False      # accents lisibles dans le JSON
    app.json.sort_keys = False
    repo = repository or PostgresRepository()

    @app.get("/")
    def index():
        return jsonify({
            "service": "API prix immobilier DVF",
            "endpoints": ["/prix?commune=...&type=...&annee=...", "/departements/<code>",
                          "/communes?q=...", "/health"],
        })

    @app.get("/health")
    def health():
        try:
            repo.ping()
        except psycopg.Error:
            return jsonify({"status": "ko", "database": "injoignable"}), 503
        return jsonify({"status": "ok", "database": "ok"})

    @app.get("/prix")
    def prix():
        commune = (request.args.get("commune") or "").strip()
        if not commune:
            raise BadRequest("Le paramètre 'commune' est obligatoire, ex. /prix?commune=Juvisy-sur-Orge")

        type_local = request.args.get("type")
        if type_local is not None:
            type_local = type_local.strip().capitalize()
            if type_local not in TYPES_VALIDES:
                raise BadRequest(f"'type' doit valoir {' ou '.join(sorted(TYPES_VALIDES))}")

        annee = request.args.get("annee")
        if annee is not None:
            if not annee.isdigit():
                raise BadRequest("'annee' doit être un nombre, ex. 2025")
            annee = int(annee)

        lignes = repo.prix_commune(commune, type_local, annee)
        if not lignes:
            raise NotFound(f"Aucune donnée pour la commune '{commune}' avec ces filtres")
        return jsonify({"commune": commune, "nb_resultats": len(lignes), "resultats": lignes})

    @app.get("/departements/<code>")
    def departement(code: str):
        lignes = repo.prix_departement(code.strip().upper())
        if not lignes:
            raise NotFound(f"Aucune donnée pour le département '{code}'")
        return jsonify({"departement": code, "resultats": lignes})

    @app.get("/communes")
    def communes():
        q = (request.args.get("q") or "").strip()
        if len(q) < 2:
            raise BadRequest("Le paramètre 'q' doit faire au moins 2 caractères")
        return jsonify({"q": q, "communes": repo.rechercher_communes(q)})

    # --- Erreurs renvoyées en JSON plutôt qu'en page HTML -----------------------
    @app.errorhandler(HTTPException)
    def http_error(err: HTTPException):
        return jsonify({"erreur": err.name, "message": err.description}), err.code

    @app.errorhandler(psycopg.Error)
    def db_error(err: psycopg.Error):
        log.exception("Erreur base de données")
        return jsonify({"erreur": "Service Unavailable",
                        "message": "Base de données indisponible"}), 503

    return app


# Permet `flask --app src.api.app run` et `gunicorn "src.api.app:create_app()"`
app = create_app()
