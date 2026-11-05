# Image légère de l'API : seulement Flask + le driver PostgreSQL (pas de Spark)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY docker/api/requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY src/__init__.py src/__init__.py
COPY src/api src/api

# l'API ne tourne pas en root
RUN useradd --create-home api
USER api

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "src.api.app:create_app()"]
