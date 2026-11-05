# DVF Pipeline — Prix de l'immobilier en France

Pipeline data de bout en bout sur les Demandes de Valeurs Foncières (DVF, data.gouv.fr) :
ingestion → PySpark → PostgreSQL → Airflow → API Flask → docker-compose.

## Avancement
- [x] Étape 1 — Ingestion des fichiers DVF (5 dernières années)
- [x] Étape 2 — Nettoyage et agrégats PySpark (prix au m²)
- [ ] Étape 3 — Chargement PostgreSQL
- [ ] Étape 4 — DAG Airflow
- [ ] Étape 5 — API Flask
- [ ] Étape 6 — docker-compose

## Démarrage
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src.ingestion.download_dvf --dept 91 --years 2   # petit jeu pour développer
python -m src.ingestion.download_dvf                        # France entière, 5 ans
python -m src.transform.clean_dvf                            # nettoyage + agrégats (Spark)
pytest
```

Prérequis pour Spark : Java 17 (`brew install openjdk@17` sur macOS).

## Règles de nettoyage (étape 2)
- Doublons exacts supprimés, seules les mutations de type « Vente » sont gardées.
- Une vente DVF peut compter plusieurs lignes qui répètent toutes le prix total : on garde
  uniquement les ventes d'**un seul logement** (appartement ou maison), dépendances autorisées.
- Surface habitable entre 9 et 1 000 m², prix entre 500 et 25 000 €/m².
- Agrégats : nombre de ventes, médiane et moyenne du prix au m², par année × commune × type
  et par année × département × type.

## Données
Source : DGFiP, DVF géolocalisées par Etalab — Licence Ouverte 2.0.
Les données ne doivent pas être utilisées pour ré-identifier des personnes.
