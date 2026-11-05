# DVF Pipeline — Prix de l'immobilier en France

Pipeline data de bout en bout sur les Demandes de Valeurs Foncières (DVF, data.gouv.fr) :
ingestion → PySpark → PostgreSQL → Airflow → API Flask → docker-compose.

## Avancement
- [x] Étape 1 — Ingestion des fichiers DVF (5 dernières années)
- [x] Étape 2 — Nettoyage et agrégats PySpark (prix au m²)
- [x] Étape 3 — Chargement PostgreSQL
- [x] Étape 4 — DAG Airflow
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
docker compose up -d postgres                                # base PostgreSQL
python -m src.load.load_postgres                             # chargement des tables
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

## Base de données (étape 3)
PostgreSQL 16 tourne dans Docker ; le schéma (`sql/init.sql`) est créé au premier démarrage,
avec clés primaires et index. Le chargement se fait avec le connecteur JDBC de Spark
(`overwrite` + `truncate` : relançable sans doublons, le schéma est conservé).

| Table | Contenu |
|---|---|
| `ventes` | une ligne par vente de logement nettoyée |
| `prix_m2_commune` | nb de ventes, prix au m² médian et moyen par année × commune × type |
| `prix_m2_departement` | idem par année × département × type |

Exemple :
```bash
docker compose exec postgres psql -U dvf -d dvf \
  -c "SELECT * FROM prix_m2_commune WHERE LOWER(nom_commune) = 'juvisy-sur-orge';"
```

## Orchestration Airflow (étape 4)
Le DAG `dvf_pipeline` (`dags/dvf_pipeline.py`) enchaîne **telecharger → nettoyer → charger**,
avec 2 relances automatiques par tâche, une exécution mensuelle et des paramètres
(`dept`, `years`) modifiables au lancement.

```bash
docker compose up -d --build      # PostgreSQL + Airflow (premier build : ~5 min)
```
Interface : http://localhost:8080 → DAG `dvf_pipeline` → *Trigger*.

Architecture Docker :
- `postgres` : base métier (tables DVF)
- `airflow-db` : base interne d'Airflow, séparée des données
- `airflow` : Airflow 3 (`standalone`) + Java + PySpark, le projet est monté dans `/opt/project`

## Données
Source : DGFiP, DVF géolocalisées par Etalab — Licence Ouverte 2.0.
Les données ne doivent pas être utilisées pour ré-identifier des personnes.
