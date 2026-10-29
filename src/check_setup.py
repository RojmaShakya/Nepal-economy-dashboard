# check_setup.py - confirms Python, pandas and the raw data file all work
import sys
import pandas as pd

print("Python:", sys.version.split()[0])
print("pandas:", pd.__version__)

# The World Bank file has 4 lines of header text before the real table,
# so we skip them with skiprows=4. utf-8-sig removes an invisible
# character (BOM) at the start of the file.
path = "data/raw/API_NPL_DS2_en_csv_v2_18651.csv"
df = pd.read_csv(path, skiprows=4, encoding="utf-8-sig")

# Each line in the file ends with a trailing comma, which pandas reads
# as an extra empty column named "Unnamed: ..." - we drop it.
df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

print("Rows, columns:", df.shape)
print("Country:", df["Country Name"].unique())
print("First 3 indicators:")
print(df["Indicator Name"].head(3).to_string(index=False))