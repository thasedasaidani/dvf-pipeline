"""
Estimer le prix d'un logement avec le modèle entraîné (models/estimateur.joblib).

Usage :
    python -m src.ml.predict --commune Juvisy-sur-Orge --type Appartement --surface 60 --pieces 3
"""

from __future__ import annotations

import argparse
import datetime as dt

import joblib
import numpy as np
import pandas as pd

from src.ml.features import preparer_features


def estimer(bundle: dict, commune: str, type_local: str, surface: float, pieces: int,
            date: dt.date | None = None) -> dict:
    ref = bundle["referentiel"]
    cle = commune.strip().lower()
    if cle not in ref.communes.index:
        raise ValueError(f"Commune inconnue du modèle : {commune}")
    infos = ref.communes.loc[cle]
    bien = pd.DataFrame([{
        "date_mutation": date or dt.date.today(),
        "code_commune": infos["code_commune"],
        "code_departement": infos["code_departement"],
        "type_local": type_local.capitalize(),
        "surface_reelle_bati": float(surface),
        "nombre_pieces_principales": int(pieces),
        "longitude": np.nan,   # position inconnue : centre de la commune
        "latitude": np.nan,
    }])
    prix = float(np.exp(bundle["modele"].predict(preparer_features(bien, ref)))[0])
    return {"commune": infos["nom_commune"], "type_local": type_local.capitalize(),
            "surface": surface, "prix_estime": round(prix, -3),
            "prix_m2_estime": round(prix / surface)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Estime le prix d'un logement")
    parser.add_argument("--commune", required=True)
    parser.add_argument("--type", default="Appartement", choices=["Appartement", "Maison"])
    parser.add_argument("--surface", type=float, required=True)
    parser.add_argument("--pieces", type=int, default=3)
    parser.add_argument("--modele", default="models/estimateur.joblib")
    args = parser.parse_args()
    r = estimer(joblib.load(args.modele), args.commune, args.type, args.surface, args.pieces)
    print(f"{r['type_local']} de {r['surface']:g} m² à {r['commune']} : "
          f"environ {r['prix_estime']:,.0f} € ({r['prix_m2_estime']:,} €/m²)".replace(",", " "))


if __name__ == "__main__":
    main()
