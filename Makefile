# Raccourcis du projet. Usage : make <commande>
.PHONY: help install test up down logs run run-france psql

help:  ## Liste des commandes
	@grep -E "^[a-z-]+:.*##" Makefile | awk -F ":.*## " '{printf "  make %-12s %s\n", $$1, $$2}'

install:  ## Crée le .venv et installe les dépendances
	python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

test:  ## Lance les tests
	.venv/bin/pytest -v

up:  ## Lance toute la plateforme (PostgreSQL, Airflow, API)
	@test -f .env || cp .env.example .env
	docker compose up -d --build
	@echo "Airflow : http://localhost:8080   API : http://localhost:8000"

down:  ## Arrête la plateforme (les données sont conservées)
	docker compose down

logs:  ## Affiche les logs des conteneurs
	docker compose logs -f --tail=100

run:  ## Déclenche le pipeline sur l'Essonne, 2 ans
	docker compose exec airflow airflow dags trigger dvf_pipeline --conf '{"dept": "91", "years": 2}'

run-france:  ## Déclenche le pipeline sur la France entière, 5 ans
	docker compose exec airflow airflow dags trigger dvf_pipeline --conf '{"dept": null, "years": 5}'

psql:  ## Ouvre une console SQL sur la base DVF
	docker compose exec postgres psql -U $${POSTGRES_USER:-dvf} -d $${POSTGRES_DB:-dvf}
