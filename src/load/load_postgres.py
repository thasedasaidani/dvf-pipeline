"""
Étape 3 — Chargement des tables Parquet (étape 2) dans PostgreSQL, via le connecteur JDBC de Spark.

Prérequis : la base tourne (docker compose up -d postgres) et le schéma sql/init.sql est créé.

Usage :
    python -m src.load.load_postgres
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from dotenv import load_dotenv

from src.transform.clean_dvf import get_spark

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("load")

JDBC_PACKAGE = "org.postgresql:postgresql:42.7.4"

# dossier Parquet (sous data/processed)  ->  table PostgreSQL
TABLES = {
    "ventes_propres": "ventes",
    "prix_m2_commune": "prix_m2_commune",
    "prix_m2_departement": "prix_m2_departement",
}


def jdbc_config() -> tuple[str, dict]:
    """URL JDBC et identifiants, lus dans les variables d'environnement (.env)."""
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "dvf")
    url = f"jdbc:postgresql://{host}:{port}/{db}"
    props = {
        "user": os.getenv("POSTGRES_USER", "dvf"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
        "driver": "org.postgresql.Driver",
    }
    return url, props


def spark_jdbc_conf() -> dict:
    """Le driver PostgreSQL est téléchargé automatiquement (Maven) au premier lancement,
    sauf si SPARK_JARS pointe vers un .jar local."""
    local_jar = os.getenv("SPARK_JARS")
    return {"spark.jars": local_jar} if local_jar else {"spark.jars.packages": JDBC_PACKAGE}


def load_table(spark, parquet_path: str, table: str, url: str, props: dict) -> int:
    df = spark.read.parquet(parquet_path)
    (
        df.write.format("jdbc")
        .option("url", url)
        .option("dbtable", table)
        .options(**props)
        # overwrite + truncate : vide la table mais garde le schéma de sql/init.sql
        # (clés primaires, index), au lieu de la recréer avec des types par défaut
        .option("truncate", "true")
        .option("batchsize", 10_000)
        .mode("overwrite")
        .save()
    )
    # vérification : on relit le nombre de lignes directement dans PostgreSQL
    nb = (
        spark.read.format("jdbc")
        .option("url", url)
        .option("query", f"SELECT COUNT(*) AS n FROM {table}")
        .options(**props)
        .load()
        .first()["n"]
    )
    log.info("Table %-20s : %s lignes", table, f"{nb:,}".replace(",", " "))
    if nb == 0:
        # contrôle qualité : une table vide fait échouer la tâche (visible dans Airflow)
        raise ValueError(f"La table {table} est vide après chargement")
    return nb


def run(processed_dir: str) -> dict:
    spark = get_spark("dvf-load", spark_jdbc_conf())
    url, props = jdbc_config()
    log.info("Connexion à %s", url)
    start = time.time()
    counts = {
        table: load_table(spark, f"{processed_dir}/{folder}", table, url, props)
        for folder, table in TABLES.items()
    }
    log.info("Chargement terminé en %s s", round(time.time() - start, 1))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Charge les tables DVF nettoyées dans PostgreSQL")
    parser.add_argument("--input", default=os.getenv("DVF_PROCESSED_DIR", "data/processed"))
    args = parser.parse_args()
    run(args.input)


if __name__ == "__main__":
    main()
