"""
Préparation des variables (features) pour prédire le prix d'un bien.

Règle d'or contre la fuite de données : toutes les statistiques par commune
(prix médian au m², position) sont calculées UNIQUEMENT sur les ventes d'entraînement,
puis appliquées aux ventes de test. Sinon le modèle « verrait » les prix qu'il doit prédire.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

COLONNES_UTILES = [
    "date_mutation", "annee", "code_departement", "code_commune", "nom_commune",
    "type_local", "valeur_fonciere", "surface_reelle_bati", "nombre_pieces_principales",
    "prix_m2", "longitude", "latitude",
]

FEATURES_NUM = [
    "surface", "log_surface", "pieces", "longitude", "latitude", "mois",
    "log_m2_commune", "log_m2_departement", "nb_ventes_commune",
]
FEATURES_CAT = ["type_local", "code_departement"]


@dataclass
class Referentiel:
    """Statistiques apprises sur le jeu d'entraînement, réutilisées pour prédire."""
    par_commune: pd.DataFrame        # index (code_commune, type_local)
    par_departement: pd.DataFrame    # index (code_departement, type_local)
    position_commune: pd.DataFrame   # index code_commune : longitude, latitude moyennes
    m2_global: float
    communes: pd.DataFrame           # nom en minuscules -> code_commune, code_departement


def construire_referentiel(train: pd.DataFrame) -> Referentiel:
    par_commune = (
        train.groupby(["code_commune", "type_local"])["prix_m2"]
        .agg(m2_commune="median", nb_ventes_commune="size")
    )
    par_departement = (
        train.groupby(["code_departement", "type_local"])["prix_m2"]
        .median().rename("m2_departement").to_frame()
    )
    position = train.groupby("code_commune")[["longitude", "latitude"]].mean()
    communes = (
        train[["nom_commune", "code_commune", "code_departement"]].drop_duplicates("code_commune")
        .assign(nom=lambda d: d["nom_commune"].str.lower()).set_index("nom")
    )
    return Referentiel(par_commune, par_departement, position,
                       float(train["prix_m2"].median()), communes)


def preparer_features(df: pd.DataFrame, ref: Referentiel) -> pd.DataFrame:
    """Transforme des ventes (ou des biens à estimer) en tableau de features."""
    X = pd.DataFrame(index=df.index)
    X["surface"] = df["surface_reelle_bati"].astype(float)
    X["log_surface"] = np.log(X["surface"])
    X["pieces"] = df["nombre_pieces_principales"].astype(float)
    X["type_local"] = df["type_local"].astype(str)
    X["code_departement"] = df["code_departement"].astype(str)
    X["mois"] = pd.to_datetime(df["date_mutation"]).dt.month.astype(float)

    # position : celle du bien, sinon le centre de sa commune
    pos = ref.position_commune.reindex(df["code_commune"]).set_index(df.index)
    X["longitude"] = df["longitude"].astype(float).fillna(pos["longitude"])
    X["latitude"] = df["latitude"].astype(float).fillna(pos["latitude"])

    # prix de référence de la commune et du département (appris sur l'entraînement)
    cle_commune = pd.MultiIndex.from_arrays([df["code_commune"], df["type_local"]])
    stats_commune = ref.par_commune.reindex(cle_commune).set_index(df.index)
    cle_dep = pd.MultiIndex.from_arrays([df["code_departement"], df["type_local"]])
    m2_dep = ref.par_departement.reindex(cle_dep)["m2_departement"].to_numpy()

    m2_dep = np.where(np.isnan(m2_dep), ref.m2_global, m2_dep)
    # commune inconnue de l'entraînement : on se rabat sur le département
    m2_commune = stats_commune["m2_commune"].to_numpy()
    m2_commune = np.where(np.isnan(m2_commune), m2_dep, m2_commune)

    X["log_m2_commune"] = np.log(m2_commune)
    X["log_m2_departement"] = np.log(m2_dep)
    X["nb_ventes_commune"] = stats_commune["nb_ventes_commune"].fillna(0).to_numpy()
    return X[FEATURES_NUM + FEATURES_CAT]


def decouper_par_annee(ventes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    """Entraînement sur les années passées, test sur la dernière année.

    C'est la situation réelle : on estime les ventes de demain avec les ventes d'hier.
    Un découpage aléatoire mélangerait les années et donnerait un score trop optimiste.
    """
    annee_test = int(ventes["annee"].max())
    train = ventes[ventes["annee"] < annee_test]
    test = ventes[ventes["annee"] == annee_test]
    if train.empty:
        raise ValueError("Il faut au moins deux années de données pour un découpage temporel")
    return train, test, annee_test
