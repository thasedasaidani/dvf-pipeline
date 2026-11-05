"""Accès aux tables DVF dans PostgreSQL (requêtes en lecture seule utilisées par l'API)."""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row


def conninfo_from_env() -> str:
    return psycopg.conninfo.make_conninfo(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "dvf"),
        user=os.getenv("POSTGRES_USER", "dvf"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


class PostgresRepository:
    def __init__(self, conninfo: str | None = None):
        self.conninfo = conninfo or conninfo_from_env()

    def _query(self, sql: str, params: dict | None = None) -> list[dict]:
        with psycopg.connect(self.conninfo, row_factory=dict_row, connect_timeout=5) as conn:
            return conn.execute(sql, params or {}).fetchall()

    def ping(self) -> bool:
        return self._query("SELECT 1 AS ok")[0]["ok"] == 1

    def prix_commune(self, commune: str, type_local: str | None = None,
                     annee: int | None = None) -> list[dict]:
        # paramètres passés séparément au driver : pas d'injection SQL possible
        sql = """
            SELECT code_commune, nom_commune, code_departement, annee, type_local,
                   nb_ventes, prix_m2_median, prix_m2_moyen
            FROM prix_m2_commune
            WHERE LOWER(nom_commune) = LOWER(%(commune)s)
              AND (%(type)s::text IS NULL OR type_local = %(type)s)
              AND (%(annee)s::int IS NULL OR annee = %(annee)s)
            ORDER BY code_commune, annee, type_local
        """
        return self._query(sql, {"commune": commune, "type": type_local, "annee": annee})

    def prix_departement(self, code: str) -> list[dict]:
        sql = """
            SELECT code_departement, annee, type_local, nb_ventes, prix_m2_median, prix_m2_moyen
            FROM prix_m2_departement
            WHERE code_departement = %(code)s
            ORDER BY annee, type_local
        """
        return self._query(sql, {"code": code})

    def rechercher_communes(self, debut: str, limite: int = 20) -> list[dict]:
        sql = """
            SELECT DISTINCT code_commune, nom_commune, code_departement
            FROM prix_m2_commune
            WHERE LOWER(nom_commune) LIKE LOWER(%(motif)s)
            ORDER BY nom_commune
            LIMIT %(limite)s
        """
        # on échappe les jokers SQL tapés par l'utilisateur (% et _)
        motif = debut.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self._query(sql, {"motif": motif, "limite": limite})
