-- Create the tables required for the project.

-- Drop dependent tables before their referenced tables.
DROP TABLE IF EXISTS observations;
DROP TABLE IF EXISTS indicators;
DROP TABLE IF EXISTS load_log;

-- Store indicator metadata.
CREATE TABLE indicators (
    indicator_code      TEXT PRIMARY KEY,
    theme               TEXT NOT NULL,
    short_label         TEXT NOT NULL,
    official_name       TEXT NOT NULL,
    source_organization TEXT,
    definition          TEXT
);

-- Store annual values for each indicator.
CREATE TABLE observations (
    indicator_code TEXT    NOT NULL REFERENCES indicators (indicator_code),
    year           INTEGER NOT NULL CHECK (year BETWEEN 1960 AND 2100),
    value          NUMERIC NOT NULL,
    PRIMARY KEY (indicator_code, year)
);

-- Track data import history.
CREATE TABLE load_log (
    load_id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loaded_at           TIMESTAMP NOT NULL DEFAULT now(),
    source_file         TEXT      NOT NULL,
    source_last_updated DATE,
    indicators_loaded   INTEGER   NOT NULL,
    rows_loaded         INTEGER   NOT NULL
);