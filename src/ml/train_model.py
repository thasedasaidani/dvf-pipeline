"""
Version Data Science — prédire le prix de vente d'un logement.

Compare 3 modèles sur les ventes nettoyées de l'étape 2 (data/processed/ventes_propres) :
  1. Référence  : prix médian au m² de la commune × surface (ce que ferait un humain)
  2. Régression linéaire (Ridge) sur le logarithme du prix
  3. Gradient boosting (HistGradientBoostingRegressor) sur le logarithme du prix

Entraînement sur les années passées, test sur la dernière année disponible.
Sorties : models/estimateur.joblib, models/metrics.json,
          reports/ml_resultats.md, reports/predictions_vs_reel.png

Usage :
    python -m src.ml.train_model
    python -m src.ml.train_model --max-lignes 300000     # plus rapide
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src.ml.features import (
    COLONNES_UTILES, FEATURES_CAT, FEATURES_NUM,
    construire_referentiel, decouper_par_annee, preparer_features,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ml")

SEED = 42


# --- Données -------------------------------------------------------------------
def charger_ventes(chemin: str) -> pd.DataFrame:
    ventes = pd.read_parquet(chemin, columns=COLONNES_UTILES)
    ventes["annee"] = ventes["annee"].astype(int)   # colonne de partition lue comme catégorie
    ventes = ventes.dropna(subset=["surface_reelle_bati", "valeur_fonciere", "prix_m2"])
    ventes["nombre_pieces_principales"] = ventes["nombre_pieces_principales"].fillna(0)
    return ventes


def echantillonner(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.sample(n=n, random_state=SEED) if len(df) > n else df


# --- Métriques -----------------------------------------------------------------
def metriques(reel: np.ndarray, predit: np.ndarray) -> dict:
    """Erreurs exprimées en % du vrai prix : lisibles par n'importe qui."""
    erreur_rel = np.abs(predit - reel) / reel
    return {
        "erreur_mediane_pct": round(float(np.median(erreur_rel) * 100), 1),
        "erreur_moyenne_pct": round(float(np.mean(erreur_rel) * 100), 1),
        "erreur_absolue_mediane_eur": int(np.median(np.abs(predit - reel))),
        "part_a_moins_de_10pct": round(float(np.mean(erreur_rel <= 0.10) * 100), 1),
        "part_a_moins_de_20pct": round(float(np.mean(erreur_rel <= 0.20) * 100), 1),
    }


# --- Modèles -------------------------------------------------------------------
def modele_lineaire() -> Pipeline:
    prep = ColumnTransformer([
        # Ridge refuse les valeurs manquantes (ex. une vente sans coordonnées GPS dans une
        # commune qui n'en a aucune) : on les remplace par la médiane, puis on met à l'échelle
        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")),
                          ("echelle", StandardScaler())]), FEATURES_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT),
    ])
    return Pipeline([("prep", prep), ("modele", Ridge(alpha=1.0))])


def modele_boosting() -> Pipeline:
    prep = ColumnTransformer(
        [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                                encoded_missing_value=-1), FEATURES_CAT)],
        remainder="passthrough", verbose_feature_names_out=False,
    )
    modele = HistGradientBoostingRegressor(
        max_iter=500, learning_rate=0.08, max_leaf_nodes=63, min_samples_leaf=40,
        categorical_features=[0, 1],          # type_local, code_departement
        early_stopping=True, validation_fraction=0.1, random_state=SEED,
    )
    return Pipeline([("prep", prep), ("modele", modele)])


# --- Graphique -----------------------------------------------------------------
def graphique_predictions(reel, predit, titre: str, chemin: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, encre, encre2, serie = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6"
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(reel), size=min(6000, len(reel)), replace=False)

    fig, ax = plt.subplots(figsize=(7, 6), dpi=150, facecolor=surface)
    ax.set_facecolor(surface)
    bornes = [max(20_000, np.percentile(reel, 0.5)), np.percentile(reel, 99.5)]
    ax.plot(bornes, bornes, color=encre2, lw=1, ls="--", zorder=3)
    ax.scatter(reel[idx], predit[idx], s=6, color=serie, alpha=0.25, linewidths=0, zorder=2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(bornes); ax.set_ylim(bornes)
    reperes = [v for v in (25e3, 50e3, 100e3, 200e3, 500e3, 1e6, 2e6, 5e6)
               if bornes[0] <= v <= bornes[1]]
    fmt = matplotlib.ticker.FuncFormatter(
        lambda v, _: f"{v/1e6:g} M€".replace(".", ",") if v >= 1e6 else f"{v/1e3:g} k€")
    for axe in (ax.xaxis, ax.yaxis):
        axe.set_major_locator(matplotlib.ticker.FixedLocator(reperes))
        axe.set_major_formatter(fmt)
        axe.set_minor_locator(matplotlib.ticker.NullLocator())
    # légende de la diagonale, dans le coin vide en bas à droite
    ax.text(0.97, 0.04, "- - -  prédiction parfaite (prédit = réel)", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color=encre2)
    ax.text(0.03, 0.96, "Chaque point = une vente de l'année de test", transform=ax.transAxes,
            ha="left", va="top", fontsize=8, color=encre2)
    ax.set_xlabel("Prix de vente réel", color=encre2)
    ax.set_ylabel("Prix prédit", color=encre2)
    ax.set_title(titre, color=encre, fontsize=11, loc="left")
    ax.tick_params(colors=encre2, labelsize=8, length=0)
    ax.grid(True, which="major", color="#e4e3df", lw=0.6)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(chemin, facecolor=surface)
    plt.close(fig)


# --- Rapport -------------------------------------------------------------------
NOMS = {"reference": "Référence (médiane commune × surface)",
        "lineaire": "Régression linéaire (Ridge)",
        "boosting": "Gradient boosting"}


def nombre(n: int) -> str:
    return f"{n:,}".replace(",", "\u202f")


def pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + " %"


def periode(annees: list[int]) -> str:
    return str(annees[0]) if len(annees) == 1 else f"{annees[0]}–{annees[-1]}"


def ecrire_rapport(resultats: dict, infos: dict, chemin: Path) -> None:
    lignes = [
        "# Prédiction du prix d'un logement — résultats",
        "",
        f"Entraînement sur {periode(infos['annees_train'])} ({nombre(infos['n_train'])} ventes), "
        f"test sur {infos['annee_test']} ({nombre(infos['n_test'])} ventes jamais vues par le modèle).",
        "",
        "| Modèle | Erreur médiane | Erreur moyenne | Ventes à ±10 % | Ventes à ±20 % |",
        "|---|---|---|---|---|",
    ]
    for cle, m in resultats.items():
        lignes.append(
            f"| {NOMS[cle]} | {pct(m['erreur_mediane_pct'])} | {pct(m['erreur_moyenne_pct'])} "
            f"| {pct(m['part_a_moins_de_10pct'])} | {pct(m['part_a_moins_de_20pct'])} |"
        )
    meilleur = min(resultats, key=lambda k: resultats[k]["erreur_mediane_pct"])
    gain = resultats["reference"]["erreur_mediane_pct"] - resultats[meilleur]["erreur_mediane_pct"]
    lignes += [
        "",
        f"Meilleur modèle : **{NOMS[meilleur]}**, erreur médiane de "
        f"**{pct(resultats[meilleur]['erreur_mediane_pct'])}** "
        f"({pct(gain).replace(' %', '')} point(s) de mieux que la référence).",
        "",
        "![Prix prédit contre prix réel](predictions_vs_reel.png)",
        "",
        "*Erreur médiane : la moitié des ventes est estimée avec un écart inférieur à ce pourcentage. "
        "L'erreur moyenne est plus élevée car quelques ventes atypiques pèsent lourd.*",
    ]
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")


# --- Programme principal -------------------------------------------------------
def run(chemin_ventes: str, max_lignes: int, dossier_modele: str, dossier_rapport: str) -> dict:
    debut = time.time()
    ventes = charger_ventes(chemin_ventes)
    log.info("Ventes chargées : %s", f"{len(ventes):,}".replace(",", " "))

    train, test, annee_test = decouper_par_annee(ventes)
    train = echantillonner(train, max_lignes)
    test = echantillonner(test, max(max_lignes // 4, 1))
    log.info("Entraînement : %s ventes (%s) — test : %s ventes (%s)",
             len(train), periode(sorted(int(a) for a in train["annee"].unique())),
             len(test), annee_test)

    ref = construire_referentiel(train)
    X_train, X_test = preparer_features(train, ref), preparer_features(test, ref)
    y_train = np.log(train["valeur_fonciere"].to_numpy())
    reel = test["valeur_fonciere"].to_numpy()

    resultats, predictions, modeles = {}, {}, {}

    # 1. Référence : aucun apprentissage, juste le prix médian de la commune
    predictions["reference"] = np.exp(X_test["log_m2_commune"].to_numpy()) * X_test["surface"].to_numpy()

    # 2 et 3. Modèles entraînés sur log(prix) : les erreurs deviennent relatives
    for cle, fabrique in [("lineaire", modele_lineaire), ("boosting", modele_boosting)]:
        t = time.time()
        modele = fabrique().fit(X_train, y_train)
        predictions[cle] = np.exp(modele.predict(X_test))
        modeles[cle] = modele
        log.info("Modèle %-10s entraîné en %.1f s", cle, time.time() - t)

    for cle, pred in predictions.items():
        resultats[cle] = metriques(reel, pred)
        log.info("%-10s erreur médiane %5.1f %% | ±20 %% : %5.1f %% des ventes",
                 cle, resultats[cle]["erreur_mediane_pct"], resultats[cle]["part_a_moins_de_20pct"])

    meilleur = min(("lineaire", "boosting"), key=lambda k: resultats[k]["erreur_mediane_pct"])

    Path(dossier_modele).mkdir(parents=True, exist_ok=True)
    Path(dossier_rapport).mkdir(parents=True, exist_ok=True)
    joblib.dump({"modele": modeles[meilleur], "referentiel": ref, "nom": meilleur},
                Path(dossier_modele) / "estimateur.joblib")

    infos = {"annees_train": sorted(int(a) for a in train["annee"].unique()),
             "annee_test": annee_test, "n_train": len(train), "n_test": len(test),
             "duree_s": round(time.time() - debut, 1), "meilleur_modele": meilleur}
    (Path(dossier_modele) / "metrics.json").write_text(
        json.dumps({"infos": infos, "resultats": resultats}, indent=2, ensure_ascii=False))
    graphique_predictions(
        reel, predictions[meilleur],
        f"{NOMS[meilleur]} — ventes {annee_test} (erreur médiane "
        f"{pct(resultats[meilleur]['erreur_mediane_pct'])})",
        Path(dossier_rapport) / "predictions_vs_reel.png")
    ecrire_rapport(resultats, infos, Path(dossier_rapport) / "ml_resultats.md")
    log.info("Terminé en %s s — rapport : %s/ml_resultats.md", infos["duree_s"], dossier_rapport)
    return {"infos": infos, "resultats": resultats}


def main() -> None:
    parser = argparse.ArgumentParser(description="Entraîne et compare les modèles de prix")
    processed = os.getenv("DVF_PROCESSED_DIR", "data/processed")
    parser.add_argument("--input", default=f"{processed}/ventes_propres")
    parser.add_argument("--max-lignes", type=int, default=1_000_000,
                        help="Nombre max de ventes d'entraînement (échantillon aléatoire)")
    parser.add_argument("--modele", default="models")
    parser.add_argument("--rapport", default="reports")
    args = parser.parse_args()
    run(args.input, args.max_lignes, args.modele, args.rapport)


if __name__ == "__main__":
    main()
