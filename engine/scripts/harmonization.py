
#!/usr/bin/env python3

"""
NASA FIRE DATA HARMONIZATION

Countries:
    South Africa, Egypt, Algeria

Years:
    2018, 2019, 2020

Sensors:
    MODIS, VIIRS

Output:
    data/harmonized/combined_harmonized_fire_data.csv

Purpose:
    Load all country/year MODIS and VIIRS CSV files,
    standardize common metadata, combine observations,
    generate unique detection IDs, and export one
    harmonized CSV.
"""

from pathlib import Path
import pandas as pd
import sys


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_DIR / "data" / "raw"

OUTPUT_DIR = PROJECT_DIR / "data" / "harmonized"

OUTPUT_FILE = OUTPUT_DIR / "combined_harmonized_fire_data.csv"

YEARS = [2018, 2019, 2020]

COUNTRIES = {
    "South_Africa": "ZAF",
    "Egypt": "EGY",
    "Algeria": "DZA"
}

SENSORS = ["MODIS", "VIIRS"]


# ==================================================
# FIND INPUT FILES
# ==================================================

def find_input_file(country, year, sensor):

    folder = RAW_DIR / str(year) / country

    if not folder.exists():
        raise FileNotFoundError(
            f"Missing folder: {folder}"
        )

    files = [
        f for f in folder.glob("*.csv")
        if sensor.lower() in f.name.lower()
    ]

    if len(files) == 0:
        raise FileNotFoundError(
            f"No {sensor} file found for {country} {year}"
        )

    if len(files) > 1:
        raise ValueError(
            f"Multiple {sensor} files found for "
            f"{country} {year}: {files}"
        )

    return files[0]


# ==================================================
# LOAD DATA
# ==================================================

def load_datasets():

    datasets = []

    print("\n========== LOADING DATA ==========\n")

    for year in YEARS:

        for country, country_code in COUNTRIES.items():

            for sensor in SENSORS:

                file_path = find_input_file(
                    country,
                    year,
                    sensor
                )

                print(f"Loading: {file_path.name}")

                df = pd.read_csv(file_path)

                # Generate unique detection IDs
                df["detection_id"] = [
                    f"{country_code}_{year}_{sensor}_{i:09d}"
                    for i in range(1, len(df) + 1)
                ]

                # Preserve source information
                df["country_name"] = country
                df["country_code"] = country_code
                df["year"] = year
                df["sensor"] = sensor
                df["source_file"] = file_path.name

                datasets.append(df)

    return datasets


# ==================================================
# STANDARDIZE DATA
# ==================================================

def standardize_dataframe(df):

    # Standardize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
    )

    required_columns = [
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "detection_id"
    ]

    for col in required_columns:

        if col not in df.columns:
            raise ValueError(
                f"Required column missing: {col}"
            )

    # Convert coordinates
    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )

    # Convert timestamps to UTC
    df["acq_datetime_utc"] = pd.to_datetime(
        df["acq_datetime_utc"],
        errors="coerce",
        utc=True
    )

    # Count invalid records before removing them
    invalid_coordinates = (
        df["latitude"].isna()
        | df["longitude"].isna()
        | ~df["latitude"].between(-90, 90)
        | ~df["longitude"].between(-180, 180)
    )

    invalid_timestamps = df["acq_datetime_utc"].isna()

    invalid_records = invalid_coordinates | invalid_timestamps

    print(
        "Invalid observations removed:",
        int(invalid_records.sum())
    )

    # Remove invalid coordinates and timestamps
    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
            "acq_datetime_utc"
        ]
    )

    # Validate coordinate ranges
    df = df[
        df["latitude"].between(-90, 90)
        &
        df["longitude"].between(-180, 180)
    ].copy()

    return df


# ==================================================
# COMBINE DATASETS
# ==================================================

def combine_datasets(datasets):

    print("\n========== COMBINING DATA ==========\n")

    combined = pd.concat(
        datasets,
        ignore_index=True,
        sort=False
    )

    print(
        "Total observations before validation:",
        len(combined)
    )

    # Check detection ID uniqueness
    if combined["detection_id"].duplicated().any():

        duplicates = combined.loc[
            combined["detection_id"].duplicated(),
            "detection_id"
        ]

        raise ValueError(
            f"Duplicate detection IDs found: {len(duplicates)}"
        )

    print("Detection IDs: All unique")

    # Standardize and validate observations
    combined = standardize_dataframe(combined)

    print(
        "Total valid observations:",
        len(combined)
    )

    return combined


# ==================================================
# SORT AND EXPORT
# ==================================================

def export_dataset(df):

    print("\n========== EXPORTING DATA ==========\n")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    df = df.sort_values(
        by=[
            "year",
            "country_code",
            "acq_datetime_utc",
            "sensor"
        ],
        kind="stable"
    ).reset_index(drop=True)

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nOutput saved successfully:")
    print(OUTPUT_FILE)

    return df


# ==================================================
# DATA QUALITY SUMMARY
# ==================================================

def print_summary(df):

    print("\n========== DATA QUALITY SUMMARY ==========\n")

    print("Total observations:", len(df))

    print("\nObservations by country:")

    print(
        df.groupby("country_name").size()
    )

    print("\nObservations by year:")

    print(
        df.groupby("year").size()
    )

    print("\nObservations by sensor:")

    print(
        df.groupby("sensor").size()
    )

    print("\nObservations by year and sensor:")

    print(
        df.groupby(
            ["year", "sensor"]
        ).size().unstack(fill_value=0)
    )

    print("\nObservations by country, year and sensor:")

    print(
        df.groupby(
            ["country_name", "year", "sensor"]
        ).size()
    )

    print("\nUnique detection IDs:")

    print(df["detection_id"].nunique())

    print("\nFinal columns:")

    print(df.columns.tolist())

    print("\n============================================")


# ==================================================
# MAIN PIPELINE
# ==================================================

def main():

    try:

        datasets = load_datasets()

        combined = combine_datasets(datasets)

        combined = export_dataset(combined)

        print_summary(combined)

        print("\nHARMONIZATION COMPLETED SUCCESSFULLY!")

    except Exception as error:

        print("\nHARMONIZATION FAILED!")
        print("Reason:", error)

        sys.exit(1)


if __name__ == "__main__":

    main()
