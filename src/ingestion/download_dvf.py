"""
Étape 1 — Ingestion des données DVF géolocalisées (data.gouv.fr).

Télécharge les fichiers annuels des N dernières années disponibles
depuis https://files.data.gouv.fr/geo-dvf/latest/csv/

Usage :
    python -m src.ingestion.download_dvf                  # 5 dernières années, France entière
    python -m src.ingestion.download_dvf --years 2        # 2 dernières années
    python -m src.ingestion.download_dvf --dept 91        # seulement l'Essonne (pratique pour développer)
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("DVF_BASE_URL", "https://files.data.gouv.fr/geo-dvf/latest/csv/")
RAW_DIR = Path(os.getenv("DVF_RAW_DIR", "data/raw"))
CHUNK_SIZE = 1024 * 1024  # 1 Mo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ingestion")


def parse_years(html: str) -> list[int]:
    """Extrait les années (dossiers 'YYYY') d'une page d'index HTML, triées.

    Tolère les liens relatifs ou absolus, avec ou sans '/' final, et les guillemets simples :
    href="2021/", href="/geo-dvf/latest/csv/2021/", href='2021' ...
    """
    pattern = r"""href=["'](?:[^"']*/)?((?:19|20)\d{2})/?["']"""
    return sorted({int(y) for y in re.findall(pattern, html)})


def probe_years(dept: str | None = None, base_url: str = BASE_URL,
                first_year: int = 2014) -> list[int]:
    """Plan B : teste l'existence du fichier pour chaque année, de l'année en cours à first_year."""
    years = []
    for year in range(date.today().year, first_year - 1, -1):
        try:
            r = requests.head(build_url(year, dept, base_url), timeout=15, allow_redirects=True)
            if r.status_code == 200:
                years.append(year)
        except requests.RequestException:
            continue
    return sorted(years)


def list_available_years(dept: str | None = None, base_url: str = BASE_URL) -> list[int]:
    years: list[int] = []
    try:
        resp = requests.get(base_url, timeout=30)
        resp.raise_for_status()
        years = parse_years(resp.text)
    except requests.RequestException as e:
        log.warning("Index illisible (%s), on teste les années une par une", e)
    if not years:
        log.info("Aucune année lue dans l'index, test des fichiers année par année…")
        years = probe_years(dept, base_url)
    if not years:
        raise RuntimeError(f"Aucune année trouvée sur {base_url}")
    return years


def build_url(year: int, dept: str | None = None, base_url: str = BASE_URL) -> str:
    if dept:
        return f"{base_url}{year}/departements/{dept}.csv.gz"
    return f"{base_url}{year}/full.csv.gz"


def download(url: str, dest: Path) -> Path:
    """Télécharge en streaming. Saute le fichier s'il est déjà complet (même taille)."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    head = requests.head(url, timeout=30, allow_redirects=True)
    head.raise_for_status()
    remote_size = int(head.headers.get("Content-Length", 0))

    if dest.exists() and remote_size and dest.stat().st_size == remote_size:
        log.info("Déjà présent, ignoré : %s", dest)
        return dest

    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Téléchargement %s (%.1f Mo)", url, remote_size / 1e6)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
    tmp.rename(dest)  # rename atomique : pas de fichier à moitié écrit si ça plante
    log.info("OK : %s", dest)
    return dest


def run(n_years: int = 5, dept: str | None = None, raw_dir: Path = RAW_DIR) -> list[Path]:
    years = list_available_years(dept)[-n_years:]
    log.info("Années retenues : %s", years)
    suffix = f"_{dept}" if dept else ""
    return [
        download(build_url(y, dept), raw_dir / f"dvf_{y}{suffix}.csv.gz")
        for y in years
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge les fichiers DVF géolocalisés")
    parser.add_argument("--years", type=int, default=5, help="Nombre d'années (défaut : 5)")
    parser.add_argument("--dept", default=None, help="Code département, ex. 91 (défaut : France entière)")
    parser.add_argument("--dest", type=Path, default=RAW_DIR, help="Dossier de destination")
    args = parser.parse_args()
    files = run(args.years, args.dept, args.dest)
    log.info("%d fichier(s) prêts dans %s", len(files), args.dest)


if __name__ == "__main__":
    main()
