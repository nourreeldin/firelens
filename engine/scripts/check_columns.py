
import pandas as pd
from pathlib import Path

# Project data directory
DATA_DIR = Path("data/raw")

# Find all CSV files
csv_files = sorted(DATA_DIR.rglob("*.csv"))

print("=" * 70)
print("NASA FIRE DATA - CSV COLUMN INSPECTION")
print("=" * 70)

print(f"\nTotal CSV files found: {len(csv_files)}")

if not csv_files:
    print("ERROR: No CSV files found in data/raw/")
    raise SystemExit(1)

# Inspect each CSV file
for file_path in csv_files:
    print("\n" + "-" * 70)
    print(f"FILE: {file_path}")
    print("-" * 70)

    try:
        # Read only the first 5 rows
        df = pd.read_csv(file_path, nrows=5)

        print("\nCOLUMNS:")
        for column in df.columns:
            print(f"  - {column}")

        print(f"\nNUMBER OF COLUMNS: {len(df.columns)}")

        print("\nSAMPLE DATA:")
        print(df.head(3).to_string(index=False))

    except Exception as error:
        print(f"ERROR reading file: {error}")

print("\n" + "=" * 70)
print("INSPECTION COMPLETED")
print("=" * 70)
