-- Schéma de la base DVF. Exécuté automatiquement par le conteneur PostgreSQL au premier démarrage.

CREATE TABLE IF NOT EXISTS ventes (
    id_mutation               TEXT PRIMARY KEY,
    date_mutation             DATE NOT NULL,
    annee                     INTEGER NOT NULL,
    code_departement          VARCHAR(3) NOT NULL,
    code_commune              VARCHAR(5) NOT NULL,
    nom_commune               TEXT NOT NULL,
    type_local                TEXT NOT NULL,
    valeur_fonciere           DOUBLE PRECISION NOT NULL,
    surface_reelle_bati       DOUBLE PRECISION NOT NULL,
    nombre_pieces_principales INTEGER,
    prix_m2                   DOUBLE PRECISION NOT NULL,
    longitude                 DOUBLE PRECISION,
    latitude                  DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_ventes_commune ON ventes (code_commune, annee);

CREATE TABLE IF NOT EXISTS prix_m2_commune (
    annee            INTEGER NOT NULL,
    code_departement VARCHAR(3) NOT NULL,
    code_commune     VARCHAR(5) NOT NULL,
    nom_commune      TEXT NOT NULL,
    type_local       TEXT NOT NULL,
    nb_ventes        BIGINT NOT NULL,
    prix_m2_median   DOUBLE PRECISION NOT NULL,
    prix_m2_moyen    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (annee, code_commune, type_local)
);
-- recherche par nom de commune, insensible à la casse (utilisée par l'API)
CREATE INDEX IF NOT EXISTS idx_prix_commune_nom ON prix_m2_commune (LOWER(nom_commune));

CREATE TABLE IF NOT EXISTS prix_m2_departement (
    annee            INTEGER NOT NULL,
    code_departement VARCHAR(3) NOT NULL,
    type_local       TEXT NOT NULL,
    nb_ventes        BIGINT NOT NULL,
    prix_m2_median   DOUBLE PRECISION NOT NULL,
    prix_m2_moyen    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (annee, code_departement, type_local)
);
