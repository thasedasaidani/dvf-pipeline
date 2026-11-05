"""Tests de l'API avec un faux dépôt de données : pas besoin de PostgreSQL."""
import psycopg
import pytest

from src.api.app import create_app

JUVISY = [
    {"code_commune": "91326", "nom_commune": "Juvisy-sur-Orge", "code_departement": "91",
     "annee": 2025, "type_local": "Appartement", "nb_ventes": 143,
     "prix_m2_median": 3493.98, "prix_m2_moyen": 3439.12},
    {"code_commune": "91326", "nom_commune": "Juvisy-sur-Orge", "code_departement": "91",
     "annee": 2025, "type_local": "Maison", "nb_ventes": 53,
     "prix_m2_median": 3640.12, "prix_m2_moyen": 3953.43},
]


class FauxDepot:
    def __init__(self, en_panne=False):
        self.en_panne = en_panne
        self.derniers_filtres = None

    def ping(self):
        if self.en_panne:
            raise psycopg.OperationalError("connexion refusée")
        return True

    def prix_commune(self, commune, type_local=None, annee=None):
        self.derniers_filtres = (commune, type_local, annee)
        if commune.lower() != "juvisy-sur-orge":
            return []
        return [r for r in JUVISY
                if (type_local is None or r["type_local"] == type_local)
                and (annee is None or r["annee"] == annee)]

    def prix_departement(self, code):
        return [{"code_departement": "91", "annee": 2025, "type_local": "Maison",
                 "nb_ventes": 5000, "prix_m2_median": 3200.0, "prix_m2_moyen": 3350.0}] \
            if code == "91" else []

    def rechercher_communes(self, debut, limite=20):
        return [{"code_commune": "91326", "nom_commune": "Juvisy-sur-Orge",
                 "code_departement": "91"}] if "juvisy".startswith(debut.lower()) else []


@pytest.fixture
def depot():
    return FauxDepot()


@pytest.fixture
def client(depot):
    return create_app(depot).test_client()


def test_prix_commune(client):
    r = client.get("/prix?commune=Juvisy-sur-Orge")
    assert r.status_code == 200
    data = r.get_json()
    assert data["nb_resultats"] == 2
    assert data["resultats"][0]["prix_m2_median"] == 3493.98


def test_prix_filtres_type_et_annee(client, depot):
    r = client.get("/prix?commune=juvisy-sur-orge&type=maison&annee=2025")
    assert r.status_code == 200
    assert depot.derniers_filtres == ("juvisy-sur-orge", "Maison", 2025)
    assert [x["type_local"] for x in r.get_json()["resultats"]] == ["Maison"]


def test_commune_obligatoire(client):
    r = client.get("/prix")
    assert r.status_code == 400
    assert "commune" in r.get_json()["message"]


@pytest.mark.parametrize("url", ["/prix?commune=Juvisy&type=Chateau",
                                 "/prix?commune=Juvisy&annee=deux-mille"])
def test_parametres_invalides(client, url):
    assert client.get(url).status_code == 400


def test_commune_inconnue_404(client):
    r = client.get("/prix?commune=Atlantis")
    assert r.status_code == 404
    assert r.get_json()["erreur"] == "Not Found"


def test_departement(client):
    assert client.get("/departements/91").status_code == 200
    assert client.get("/departements/99").status_code == 404


def test_recherche_communes(client):
    r = client.get("/communes?q=juv")
    assert r.get_json()["communes"][0]["nom_commune"] == "Juvisy-sur-Orge"
    assert client.get("/communes?q=j").status_code == 400


def test_health_ok_et_base_en_panne():
    assert create_app(FauxDepot()).test_client().get("/health").status_code == 200
    r = create_app(FauxDepot(en_panne=True)).test_client().get("/health")
    assert r.status_code == 503


def test_json_avec_accents_lisibles(client):
    # "donnée" doit apparaître tel quel, pas sous la forme "donn\u00e9e"
    assert "Aucune donnée".encode() in client.get("/prix?commune=Atlantis").data
