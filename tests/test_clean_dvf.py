from src.transform.clean_dvf import KEYS_COMMUNE, aggregate_prix_m2, cast_columns, clean

COLS = ["id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "code_departement",
        "code_commune", "nom_commune", "type_local", "surface_reelle_bati",
        "nombre_pieces_principales", "longitude", "latitude"]


def ligne(id_mut, prix, type_local, surface, nature="Vente", commune="91326"):
    """Une ligne DVF brute (tout en texte, comme dans le CSV)."""
    return (id_mut, "2025-03-15", nature, str(prix), "91", commune, "Juvisy-sur-Orge",
            type_local, None if surface is None else str(surface), "3", "2.37", "48.69")


SCHEMA = ", ".join(f"{c} string" for c in COLS)  # comme le CSV brut : tout en texte


def nettoyer(spark, lignes):
    df = spark.createDataFrame(lignes, SCHEMA)
    return clean(cast_columns(df))


def test_vente_simple_et_prix_m2(spark):
    res = nettoyer(spark, [ligne("A", 200000, "Appartement", 50)]).collect()
    assert len(res) == 1
    assert res[0]["prix_m2"] == 4000.0
    assert res[0]["annee"] == 2025


def test_doublons_exacts_supprimes(spark):
    l = ligne("A", 200000, "Appartement", 50)
    assert nettoyer(spark, [l, l]).count() == 1


def test_hors_vente_exclue(spark):
    assert nettoyer(spark, [ligne("A", 200000, "Appartement", 50, nature="Echange")]).count() == 0


def test_vente_de_deux_logements_exclue(spark):
    # le prix est le total des deux logements : prix au m² faux, on écarte la vente
    lignes = [ligne("A", 400000, "Appartement", 50), ligne("A", 400000, "Appartement", 60)]
    assert nettoyer(spark, lignes).count() == 0


def test_logement_avec_dependance_garde(spark):
    lignes = [ligne("A", 210000, "Appartement", 50), ligne("A", 210000, "Dépendance", None)]
    res = nettoyer(spark, lignes).collect()
    assert len(res) == 1 and res[0]["type_local"] == "Appartement"


def test_logement_avec_local_commercial_exclu(spark):
    lignes = [ligne("A", 500000, "Maison", 100),
              ligne("A", 500000, "Local industriel. commercial ou assimilé", 80)]
    assert nettoyer(spark, lignes).count() == 0


def test_valeurs_aberrantes_exclues(spark):
    lignes = [
        ligne("A", 200000, "Appartement", 5),      # surface trop petite
        ligne("B", 1000, "Maison", 100),           # 10 €/m²
        ligne("C", 9000000, "Appartement", 40),    # 225 000 €/m²
        ligne("D", 300000, "Maison", 100),         # OK
    ]
    res = nettoyer(spark, lignes).collect()
    assert [r["id_mutation"] for r in res] == ["D"]


def test_agregat_mediane_par_commune(spark):
    lignes = [ligne(i, prix, "Appartement", 50) for i, prix in
              [("A", 150000), ("B", 200000), ("C", 250000)]]
    agg = aggregate_prix_m2(nettoyer(spark, lignes), KEYS_COMMUNE).collect()
    assert len(agg) == 1
    assert agg[0]["nb_ventes"] == 3
    assert agg[0]["prix_m2_median"] == 4000.0


def test_ligne_sans_commune_exclue(spark):
    l = list(ligne("A", 200000, "Appartement", 50))
    l[6] = None  # nom_commune manquant
    assert nettoyer(spark, [tuple(l)]).count() == 0


def test_valeurs_illisibles_ne_font_pas_planter(spark):
    l = list(ligne("A", 200000, "Appartement", 50))
    l[3] = "pas-un-prix"
    lignes = [tuple(l), ligne("B", 200000, "Appartement", 50)]
    assert [r["id_mutation"] for r in nettoyer(spark, lignes).collect()] == ["B"]
