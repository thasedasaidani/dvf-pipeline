"""Vérifie la structure du DAG. Ignoré si Airflow n'est pas installé dans l'environnement local."""
from pathlib import Path

import pytest

pytest.importorskip("airflow")

DAG_FILE = Path(__file__).resolve().parent.parent / "dags" / "dvf_pipeline.py"


def test_dag_structure():
    import importlib.util

    spec = importlib.util.spec_from_file_location("dvf_pipeline", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dag = module.dag

    assert dag.dag_id == "dvf_pipeline"
    assert {t.task_id for t in dag.tasks} == {"telecharger", "nettoyer", "charger"}
    assert dag.get_task("telecharger").downstream_task_ids == {"nettoyer"}
    assert dag.get_task("nettoyer").downstream_task_ids == {"charger"}
    assert all(t.retries == 2 for t in dag.tasks)
