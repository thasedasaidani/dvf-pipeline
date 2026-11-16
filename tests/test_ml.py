"""Tests de la partie Data Science (préparation des features, métriques, estimation)."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.ml.features import construire_referentiel, decouper_par_annee, preparer_features
from src.ml.train_model import metriques


def vente(id_, annee, commune, prix_m2, surface=50, type_local="Appartement", dep="91"):
    return {"id_mutation": id_, "date_mutation": dt.date(annee, 6, 1), "annee": annee,
            "code_departement": dep, "code_commune": commune, "nom_commune": f"Ville {commune}",
            "type_local": type_local, "valeur_fonciere": prix_m2 * surface,
            "surface_reelle_bati": surface, "nombre_pieces_principales": 3,
            "prix_m2": prix_m2, "longitude": 2.3, "latitude": 48.7}


@pytest.fixture
def ventes():
    return pd.DataFrame([
        vente("a", 2024, "91001", 3000), vente("b", 2024, "91001", 4000),
        vente("c", 2024, "91002", 2000),
        vente("d", 2025, "91001", 9999),     # prix de test : ne doit PAS influencer les features
        vente("e", 2025, "91999", 5000),     # commune absente de l'entraînement
    ])


def test_decoupage_temporel(ventes):
    train, test, annee = decouper_par_annee(ventes)
    assert annee == 2025
    assert set(train["annee"]) == {2024} and set(test["annee"]) == {2025}


def test_pas_de_fuite_de_donnees(ventes):
    train, test, _ = decouper_par_annee(ventes)
    X_test = preparer_features(test, construire_referentiel(train))
    # médiane de 91001 calculée sur 2024 seulement : (3000 + 4000) / 2, pas 9999
    assert np.exp(X_test.loc[3, "log_m2_commune"]) == pytest.approx(3500)


def test_commune_inconnue_prend_le_departement(ventes):
    train, test, _ = decouper_par_annee(ventes)
    X_test = preparer_features(test, construire_referentiel(train))
    # médiane du 91 en 2024 sur 3000, 4000, 2000 = 3000
    assert np.exp(X_test.loc[4, "log_m2_commune"]) == pytest.approx(3000)
    assert X_test.loc[4, "nb_ventes_commune"] == 0


def test_un_seul_millesime_refuse(ventes):
    with pytest.raises(ValueError):
        decouper_par_annee(ventes[ventes["annee"] == 2024])


def test_metriques():
    m = metriques(np.array([100.0, 200.0, 400.0]), np.array([110.0, 200.0, 300.0]))
    assert m["erreur_mediane_pct"] == 10.0          # erreurs : 10 %, 0 %, 25 %
    assert m["part_a_moins_de_10pct"] == pytest.approx(66.7)
    assert m["part_a_moins_de_20pct"] == pytest.approx(66.7)


def test_estimation_bout_en_bout(ventes):
    from sklearn.dummy import DummyRegressor
    from src.ml.predict import estimer

    train, _, _ = decouper_par_annee(ventes)
    ref = construire_referentiel(train)
    X = preparer_features(train, ref)
    modele = DummyRegressor(strategy="constant", constant=np.log(200_000)).fit(X, np.zeros(len(X)))
    r = estimer({"modele": modele, "referentiel": ref}, "ville 91001", "appartement", 50, 2)
    assert r["prix_estime"] == 200_000 and r["prix_m2_estime"] == 4000
    with pytest.raises(ValueError):
        estimer({"modele": modele, "referentiel": ref}, "Atlantis", "Maison", 80, 4)


def test_modele_lineaire_accepte_les_positions_manquantes(ventes):
    # une commune dont aucune vente n'a de coordonnées GPS : longitude et latitude restent vides
    from src.ml.train_model import modele_lineaire

    ventes.loc[ventes["code_commune"] == "91002", ["longitude", "latitude"]] = np.nan
    train, _, _ = decouper_par_annee(ventes)
    ref = construire_referentiel(train)
    X = preparer_features(train, ref)
    assert X["longitude"].isna().any()
    modele = modele_lineaire().fit(X, np.log(train["valeur_fonciere"].to_numpy()))
    assert np.isfinite(modele.predict(X)).all()
