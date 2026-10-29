
import pandas as pd

# --- 1. Input and output paths ---

RAW = "data/raw/API_NPL_DS2_en_csv_v2_18651.csv"
META = "data/raw/Metadata_Indicator_API_NPL_DS2_en_csv_v2_18651.csv"
OUTPUT = "data/processed/indicator_coverage.csv"


# --- 2. Load raw data and indicator metadata ---

df = pd.read_csv(RAW, skiprows=4, encoding="utf-8-sig")
df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

meta = pd.read_csv(META, encoding="utf-8-sig")
meta = meta.loc[:, ~meta.columns.str.startswith("Unnamed")]

# Keep one metadata record per indicator code
meta = meta.drop_duplicates(subset="INDICATOR_CODE")

# Find columns containing years
year_cols = [col for col in df.columns if col.isdigit()]

print("First year:", year_cols[0])
print("Last year:", year_cols[-1])
print("Number of years:", len(year_cols))


# --- 3. Basic data checks ---

print("\n--- Basic checks ---")

print("Number of rows:", len(df))

print(
    "Duplicate indicator codes:",
    df["Indicator Code"].duplicated().sum()
)

non_missing = df[year_cols].notna().sum(axis=1)

print("Indicators with no data:", (non_missing == 0).sum())
print("Indicators with 20+ years of data:", (non_missing >= 20).sum())
print("Indicators with 40+ years of data:", (non_missing >= 40).sum())


# --- 4. Match indicators with metadata ---

# Match raw data to metadata using the indicator code
data = df.merge(
    meta[["INDICATOR_CODE", "INDICATOR_NAME"]],
    left_on="Indicator Code",
    right_on="INDICATOR_CODE",
    how="left"
)

# Fall back to the raw indicator name when metadata is unavailable
data["label"] = data["INDICATOR_NAME"].fillna(data["Indicator Name"])

missing_metadata = data["INDICATOR_NAME"].isna().sum()

print("\n--- Metadata check ---")
print("Indicators without a metadata definition:", missing_metadata)
print("Indicators included in coverage report:", len(data))


# --- 4.1. Classify indicators by theme ---

def get_theme(code):

    # Economy
    if code.startswith(("NY.GDP", "NV.")):
        return "Economy"

    # Prices
    elif code.startswith("FP.CPI"):
        return "Prices"

    # External trade and financial flows
    elif code.startswith(("BX.", "BM.", "TX.", "NE.", "FI.")):
        return "External"

    # Population and social development
    elif code.startswith(("SP.", "SL.", "SE.", "SH.", "EG.", "IT.")):
        return "People"

    # Anything that does not match the rules above
    else:
        return "Other"


data["theme"] = data["Indicator Code"].apply(get_theme)

# --- 5. Build indicator coverage report ---

coverage_rows = []

for _, row in data.iterrows():

    # Normalize annual observations and exclude missing values
    values = pd.to_numeric(row[year_cols], errors="coerce").dropna()

    if len(values) > 0:
        first_year = int(values.index[0])
        last_year = int(values.index[-1])

        # Count missing years between the first and last values
        year_span = last_year - first_year + 1
        gaps = year_span - len(values)

        latest_value = round(values.iloc[-1], 2)

    else:
        first_year = None
        last_year = None
        gaps = None
        latest_value = None

   
    coverage_rows.append({
        "theme": row["theme"],
        "code": row["Indicator Code"],
        "label": row["label"],
        "first_year": first_year,
        "last_year": last_year,
        "years_with_data": len(values),
        "gaps_inside_span": gaps,
        "latest_value": latest_value
    })


# Assemble and export the coverage report
cov = pd.DataFrame(coverage_rows)

pd.set_option("display.width", 200)
pd.set_option("display.float_format", "{:,.2f}".format)

print("\n--- Indicator coverage ---")
print(cov.head(20).to_string(index=False))

cov.to_csv(OUTPUT, index=False)

print("\nSaved:", OUTPUT)


# --- 6. Prepare indicators for validation ---

# Reference indicators for the validation checks below
check_codes = [
    "NV.AGR.TOTL.ZS",
    "NV.IND.TOTL.ZS",
    "NV.SRV.TOTL.ZS",
    "BX.TRF.PWKR.CD.DT",
    "BX.TRF.PWKR.DT.GD.ZS",
    "NY.GDP.MKTP.CD",
    "FP.CPI.TOTL.ZG",
    "NY.GDP.MKTP.KD.ZG",
    "BX.KLT.DINV.WD.GD.ZS"
]

check_data = df[df["Indicator Code"].isin(check_codes)]

# Reshape from one row per indicator to one row per year
long = check_data.melt(
    id_vars=["Indicator Code"],
    value_vars=year_cols,
    var_name="year",
    value_name="value"
)

long["year"] = long["year"].astype(int)
long["value"] = pd.to_numeric(long["value"], errors="coerce")

# Align indicators by year for validation
wide = long.pivot(
    index="year",
    columns="Indicator Code",
    values="value"
)


# --- 7. Validate economic sector shares ---

print("\n--- Sanity check 1: Sector shares ---")

sector_codes = [
    "NV.AGR.TOTL.ZS",
    "NV.IND.TOTL.ZS",
    "NV.SRV.TOTL.ZS"
]

if all(code in wide.columns for code in sector_codes):

    shares = wide[sector_codes].dropna().sum(axis=1)

    if len(shares) > 0:
        print("Smallest total:", round(shares.min(), 1))
        print("Largest total:", round(shares.max(), 1))
    else:
        print("Not enough data for this check.")

else:
    print("One or more sector indicators are missing.")


# --- 8. Validate remittance ratios ---

print("\n--- Sanity check 2: Remittances ---")

remittance_codes = [
    "BX.TRF.PWKR.CD.DT",
    "NY.GDP.MKTP.CD",
    "BX.TRF.PWKR.DT.GD.ZS"
]

if all(code in wide.columns for code in remittance_codes):

    # Calculate remittances as a percentage of GDP
    calculated = (
        wide["BX.TRF.PWKR.CD.DT"]
        / wide["NY.GDP.MKTP.CD"]
        * 100
    )

    reported = wide["BX.TRF.PWKR.DT.GD.ZS"]

    difference = (calculated - reported).dropna()

    if len(difference) > 0:
        print(
            "Largest difference (percentage points):",
            round(difference.abs().max(), 2)
        )
    else:
        print("Not enough overlapping data for this check.")

else:
    print("One or more remittance indicators are missing.")


# --- 9. Check inflation and GDP growth ranges ---

print("\n--- Sanity check 3: Value ranges ---")

for code in ["FP.CPI.TOTL.ZG", "NY.GDP.MKTP.KD.ZG"]:

    if code in wide.columns:

        values = wide[code].dropna()

        if len(values) > 0:
            min_year = values.idxmin()
            max_year = values.idxmax()

            print(
                f"{code}: minimum {values.min():.1f} "
                f"(year {min_year}), maximum {values.max():.1f} "
                f"(year {max_year})"
            )

        else:
            print(f"{code}: no available values")

    else:
        print(f"{code}: indicator not found")


# --- 10. Identify gaps in FDI observations ---

print("\n--- FDI gap years ---")

fdi_code = "BX.KLT.DINV.WD.GD.ZS"

if fdi_code in wide.columns:

    fdi = wide[fdi_code].dropna()

    if len(fdi) > 0:

        first_year = int(fdi.index.min())
        last_year = int(fdi.index.max())

        # Define the full reporting period
        all_years = set(range(first_year, last_year + 1))

        # Identify years with reported observations
        available_years = set(fdi.index.astype(int))

        # Find missing years within the reporting period
        missing_years = sorted(all_years - available_years)

        print(missing_years)

    else:
        print("No FDI data available.")

else:
    print("FDI indicator not found.")
