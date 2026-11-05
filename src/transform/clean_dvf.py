"""
Étape 2 — Nettoyage des données DVF et calcul des prix au m² avec PySpark.

Entrée  : data/raw/*.csv.gz            (fichiers téléchargés à l'étape 1)
Sorties : data/processed/ventes_propres/        une ligne par vente de logement, nettoyée
          data/processed/prix_m2_commune/       médiane du prix au m² par année, commune, type de bien
          data/processed/prix_m2_departement/   idem par département

Usage :
    python -m src.transform.clean_dvf
    python -m src.transform.clean_dvf --input data/raw --output data/processed
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from dotenv import load_dotenv
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("transform")

# --- Règles métier (documentées dans le README) --------------------------------
TYPES_LOGEMENT = ["Appartement", "Maison"]
SURFACE_MIN, SURFACE_MAX = 9, 1000          # m² : en dessous de 9 m², ce n'est pas un logement
PRIX_M2_MIN, PRIX_M2_MAX = 500, 25_000      # €/m² : au-delà, erreurs de saisie ou ventes atypiques


def get_spark(app_name: str = "dvf-pipeline") -> SparkSession:
    return (
        SparkSession.builder.appName(app_name)
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "4g"))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


def read_raw(spark: SparkSession, path: str) -> DataFrame:
    """Lit les CSV DVF bruts. Tout est lu en texte : les types sont fixés dans cast_columns."""
    return spark.read.option("header", True).csv(path)


def cast_columns(df: DataFrame) -> DataFrame:
    """Garde les colonnes utiles et leur donne le bon type."""
    return df.select(
        F.col("id_mutation"),
        F.to_date("date_mutation").alias("date_mutation"),
        F.col("nature_mutation"),
        F.col("valeur_fonciere").cast("double"),
        F.col("code_departement"),
        F.col("code_commune"),
        F.col("nom_commune"),
        F.col("type_local"),
        F.col("surface_reelle_bati").cast("double"),
        F.col("nombre_pieces_principales").cast("int"),
        F.col("longitude").cast("double"),
        F.col("latitude").cast("double"),
    ).withColumn("annee", F.year("date_mutation"))


def clean(df: DataFrame) -> DataFrame:
    """
    Produit une ligne par vente d'un logement unique, avec son prix au m².

    Particularité DVF : une vente (id_mutation) peut avoir plusieurs lignes (plusieurs locaux,
    plusieurs parcelles), et chaque ligne répète le prix TOTAL de la vente. On ne garde donc
    que les ventes portant sur un seul logement (avec éventuellement des dépendances : cave,
    parking), sinon le prix au m² serait faux.
    """
    df = (
        df.dropDuplicates()
        .filter(F.col("nature_mutation") == "Vente")
        .filter(F.col("valeur_fonciere") > 0)
    )

    # Nombre de locaux "principaux" (hors dépendances) par vente
    par_vente = Window.partitionBy("id_mutation")
    est_local_principal = F.col("type_local").isNotNull() & (F.col("type_local") != "Dépendance")
    df = df.withColumn(
        "nb_locaux", F.sum(F.when(est_local_principal, 1).otherwise(0)).over(par_vente)
    )

    ventes = (
        df.filter(F.col("type_local").isin(TYPES_LOGEMENT))
        .filter(F.col("nb_locaux") == 1)
        # une même vente peut apparaître sur plusieurs parcelles : une seule ligne par vente
        .dropDuplicates(["id_mutation"])
        .filter(F.col("surface_reelle_bati").between(SURFACE_MIN, SURFACE_MAX))
        .withColumn("prix_m2", F.round(F.col("valeur_fonciere") / F.col("surface_reelle_bati"), 2))
        .filter(F.col("prix_m2").between(PRIX_M2_MIN, PRIX_M2_MAX))
    )

    return ventes.select(
        "id_mutation", "date_mutation", "annee", "code_departement", "code_commune",
        "nom_commune", "type_local", "valeur_fonciere", "surface_reelle_bati",
        "nombre_pieces_principales", "prix_m2", "longitude", "latitude",
    )


def aggregate_prix_m2(ventes: DataFrame, keys: list[str]) -> DataFrame:
    """Médiane, moyenne et nombre de ventes du prix au m² par groupe."""
    return (
        ventes.groupBy(*keys)
        .agg(
            F.count("*").alias("nb_ventes"),
            F.percentile_approx("prix_m2", 0.5).alias("prix_m2_median"),
            F.round(F.avg("prix_m2"), 2).alias("prix_m2_moyen"),
        )
        .orderBy(*keys)
    )


KEYS_COMMUNE = ["annee", "code_departement", "code_commune", "nom_commune", "type_local"]
KEYS_DEPARTEMENT = ["annee", "code_departement", "type_local"]


def run(input_path: str, output_path: str) -> dict:
    spark = get_spark()
    start = time.time()

    brut = read_raw(spark, input_path)
    nb_brut = brut.count()
    log.info("Lignes brutes lues : %s", f"{nb_brut:,}".replace(",", " "))

    ventes = clean(cast_columns(brut)).cache()
    nb_ventes = ventes.count()
    log.info("Ventes de logements retenues : %s", f"{nb_ventes:,}".replace(",", " "))

    ventes.write.mode("overwrite").partitionBy("annee").parquet(f"{output_path}/ventes_propres")
    aggregate_prix_m2(ventes, KEYS_COMMUNE).write.mode("overwrite").parquet(
        f"{output_path}/prix_m2_commune")
    aggregate_prix_m2(ventes, KEYS_DEPARTEMENT).write.mode("overwrite").parquet(
        f"{output_path}/prix_m2_departement")

    duree = round(time.time() - start, 1)
    log.info("Terminé en %s s — résultats dans %s", duree, output_path)
    return {"lignes_brutes": nb_brut, "ventes_retenues": nb_ventes, "duree_s": duree}


def main() -> None:
    parser = argparse.ArgumentParser(description="Nettoie les données DVF et calcule les prix au m²")
    parser.add_argument("--input", default=os.getenv("DVF_RAW_DIR", "data/raw") + "/*.csv.gz")
    parser.add_argument("--output", default=os.getenv("DVF_PROCESSED_DIR", "data/processed"))
    args = parser.parse_args()
    run(args.input, args.output)


if __name__ == "__main__":
    main()
