"""
DAG Airflow du pipeline DVF : téléchargement -> nettoyage Spark -> chargement PostgreSQL.

Chaque tâche lance un des scripts du projet (src/...), exactement comme à la main.
Interface : http://localhost:8080
"""

import os
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG, Param

PROJECT_DIR = os.getenv("DVF_PROJECT_DIR", "/opt/project")

DOC = """
### Pipeline DVF — prix de l'immobilier
1. **telecharger** : fichiers DVF depuis data.gouv.fr (`data/raw`)
2. **nettoyer** : nettoyage et prix au m² avec PySpark (`data/processed`)
3. **charger** : chargement dans PostgreSQL (tables `ventes`, `prix_m2_commune`, `prix_m2_departement`)

Paramètres (bouton *Trigger*) : `dept` (vide = France entière) et `years` (nombre d'années).
"""

with DAG(
    dag_id="dvf_pipeline",
    description="Prix de l'immobilier en France à partir des données DVF",
    doc_md=DOC,
    # DVF est mis à jour 2 fois par an : une vérification mensuelle suffit
    schedule="0 6 1 * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    params={
        "dept": Param("91", type=["null", "string"],
                      description="Code département (ex. 91). Vide = France entière."),
        "years": Param(2, type="integer", minimum=1, maximum=10,
                       description="Nombre d'années à télécharger"),
    },
    tags=["dvf", "spark", "postgres"],
) as dag:

    telecharger = BashOperator(
        task_id="telecharger",
        bash_command=(
            "python -m src.ingestion.download_dvf --years {{ params.years }}"
            "{% if params.dept %} --dept {{ params.dept }}{% endif %}"
        ),
        cwd=PROJECT_DIR,
    )

    nettoyer = BashOperator(
        task_id="nettoyer",
        bash_command="python -m src.transform.clean_dvf",
        cwd=PROJECT_DIR,
        execution_timeout=timedelta(hours=1),
    )

    charger = BashOperator(
        task_id="charger",
        bash_command="python -m src.load.load_postgres",
        cwd=PROJECT_DIR,
    )

    telecharger >> nettoyer >> charger
