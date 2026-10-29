
# load_to_postgres.py - Load World Bank data into PostgreSQL

import os
import sys
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

RAW = "data/raw/API_NPL_DS2_en_csv_v2_18651.csv"
META = "data/raw/Metadata_Indicator_API_NPL_DS2_en_csv_v2_18651.csv"
SELECTED = "config/indicators_selected.csv"

# Read the last-updated date from the source file.
last_updated = None

with open(RAW, encoding="utf-8-sig") as f:
    for line in f:
        if line.startswith('"Last Updated Date"'):
            last_updated = line.split(",")[1].strip().strip('"')
            break

print("World Bank file last updated:", last_updated)

# Read the data and selected indicator list.
df = pd.read_csv(RAW, skiprows=4, encoding="utf-8-sig")
df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

year_cols = [col for col in df.columns if col.isdigit()]

selected = pd.read_csv(SELECTED)
selected["indicator_code"] = selected["indicator_code"].str.strip()
codes = selected["indicator_code"].tolist()

# Combine indicator details from the source and metadata files.
names = df[["Indicator Code", "Indicator Name"]].rename(
    columns={
        "Indicator Code": "indicator_code",
        "Indicator Name": "official_name",
    }
)

meta = pd.read_csv(META, encoding="utf-8-sig")
meta = meta.rename(
    columns={
        "INDICATOR_CODE": "indicator_code",
        "SOURCE_NOTE": "definition",
        "SOURCE_ORGANIZATION": "source_organization",
    }
)

meta = meta[["indicator_code", "definition", "source_organization"]]

indicators = selected.merge(names, on="indicator_code", how="left")
indicators = indicators.merge(meta, on="indicator_code", how="left")

indicators = indicators[
    [
        "indicator_code",
        "theme",
        "short_label",
        "official_name",
        "source_organization",
        "definition",
    ]
]

if len(indicators) != len(selected):
    sys.exit("Stopped: indicator count does not match the selected list.")

# Reshape annual data into one row per indicator and year.
only_chosen = df[df["Indicator Code"].isin(codes)]

observations = only_chosen.melt(
    id_vars=["Indicator Code"],
    value_vars=year_cols,
    var_name="year",
    value_name="value",
)

observations = observations.rename(
    columns={"Indicator Code": "indicator_code"}
)

# Exclude missing values and prepare the year column.
observations = observations.dropna(subset=["value"])
observations["year"] = observations["year"].astype(int)
observations = observations.sort_values(["indicator_code", "year"])

# Validate the data before loading it.
if indicators["official_name"].isna().any():
    sys.exit("Stopped: some indicator names are missing.")

if observations.empty:
    sys.exit("Stopped: no observations found.")

if observations.duplicated(["indicator_code", "year"]).any():
    sys.exit("Stopped: duplicate indicator-year records found.")

if observations["value"].isna().any():
    sys.exit("Stopped: missing observation values found.")

print("Indicators to load:", len(indicators))
print("Observations to load:", len(observations))
print("Data validation passed.")

# Connect to PostgreSQL using environment variables.
load_dotenv()

db_url = URL.create(
    "postgresql+psycopg2",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME"),
)

engine = create_engine(db_url)


# Load the data and record the import in one transaction.
with engine.begin() as conn:
    conn.execute(text("DELETE FROM observations"))
    conn.execute(text("DELETE FROM indicators"))

    indicators.to_sql("indicators", conn, if_exists="append", index=False)
    observations.to_sql("observations", conn, if_exists="append", index=False)

    conn.execute(
        text("""
            INSERT INTO load_log
                (source_file, source_last_updated, indicators_loaded, rows_loaded)
            VALUES (:file, :updated, :n_ind, :n_obs)
        """),
        {
            "file": os.path.basename(RAW),
            "updated": last_updated,
            "n_ind": len(indicators),
            "n_obs": len(observations),
        },
    )

# Verify the loaded data.
with engine.connect() as conn:
    n_ind = conn.execute(text("SELECT COUNT(*) FROM indicators")).scalar()
    n_obs = conn.execute(text("SELECT COUNT(*) FROM observations")).scalar()

if n_ind != len(indicators) or n_obs != len(observations):
    sys.exit("Error: database row counts do not match.")

print("Indicators loaded:", n_ind)
print("Observations loaded:", n_obs)
print("All checks passed.")

engine.dispose()
