
#!/usr/bin/env python3

"""
NASA FIRE DATA - HARMONIZED DATASET VALIDATION

Validates:
    1. Dataset integrity
    2. Missing values
    3. Detection ID uniqueness
    4. Geographic coordinates
    5. UTC timestamps
    6. Country, year, and sensor metadata
    7. Observation distribution

Input:
    data/harmonized/combined_harmonized_fire_data.csv

Output:
    data/validation/harmonized_validation_summary.csv
    data/validation/observations_by_group.csv
    data/validation/invalid_observations.csv
"""

from pathlib import Path
import pandas as pd
import sys


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_DIR
    / "data"
    / "harmonized"
    / "combined_harmonized_fire_data.csv"
)

OUTPUT_DIR = PROJECT_DIR / "data" / "validation"

EXPECTED_YEARS = [2018, 2019, 2020]

EXPECTED_COUNTRIES = {
    "South_Africa": "ZAF",
    "Egypt": "EGY",
    "Algeria": "DZA"
}

EXPECTED_SENSORS = ["MODIS", "VIIRS"]


# ==================================================
# LOAD DATA
# ==================================================

def load_dataset():

    print("\n========== LOADING HARMONIZED DATA ==========\n")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Harmonized dataset not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print("Dataset loaded successfully.")
    print("Total observations:", len(df))
    print("Total columns:", len(df.columns))

    return df


# ==================================================
# VALIDATE REQUIRED COLUMNS
# ==================================================

def validate_columns(df):

    print("\n========== COLUMN VALIDATION ==========\n")

    required_columns = [
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "detection_id",
        "country_name",
        "country_code",
        "year",
        "sensor",
        "instrument"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    print("All required columns are present.")

    return True


# ==================================================
# DATA QUALITY VALIDATION
# ==================================================

def validate_data(df):

    print("\n========== DATA QUALITY VALIDATION ==========\n")

    results = []

    # Coordinates
    latitude = pd.to_numeric(
        df["latitude"],
        errors="coerce"
    )

    longitude = pd.to_numeric(
        df["longitude"],
        errors="coerce"
    )

    invalid_coordinates = (
        latitude.isna()
        | longitude.isna()
        | ~latitude.between(-90, 90)
        | ~longitude.between(-180, 180)
    )

    # Timestamps
    timestamps = pd.to_datetime(
        df["acq_datetime_utc"],
        errors="coerce",
        utc=True
    )

    invalid_timestamps = timestamps.isna()

    # Detection IDs
    missing_ids = df["detection_id"].isna()

    duplicate_ids = (
        df["detection_id"].duplicated(keep=False)
        & ~missing_ids
    )

    # Country metadata
    invalid_countries = (
        ~df["country_name"].isin(EXPECTED_COUNTRIES)
        | df["country_code"].isna()
    )

    expected_codes = df["country_name"].map(
        EXPECTED_COUNTRIES
    )

    invalid_country_codes = (
        expected_codes.isna()
        | df["country_code"].ne(expected_codes)
    )

    # Year metadata
    years = pd.to_numeric(
        df["year"],
        errors="coerce"
    )

    invalid_years = ~years.isin(EXPECTED_YEARS)

    # Sensor metadata
    invalid_sensors = ~df["sensor"].isin(
        EXPECTED_SENSORS
    )

    invalid_instruments = (
        df["instrument"].astype(str).str.upper()
        != df["sensor"].astype(str).str.upper()
    )

    checks = {
        "Invalid coordinates": invalid_coordinates,
        "Invalid timestamps": invalid_timestamps,
        "Missing detection IDs": missing_ids,
        "Duplicate detection IDs": duplicate_ids,
        "Invalid countries": invalid_countries,
        "Invalid country codes": invalid_country_codes,
        "Invalid years": invalid_years,
        "Invalid sensors": invalid_sensors,
        "Sensor/instrument mismatch": invalid_instruments
    }

    for check_name, mask in checks.items():

        count = int(mask.sum())

        status = "PASS" if count == 0 else "FAIL"

        results.append({
            "validation_check": check_name,
            "invalid_count": count,
            "status": status
        })

        print(f"{check_name}: {count} [{status}]")

    # Missing values in important columns
    important_columns = [
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "detection_id",
        "country_name",
        "country_code",
        "year",
        "sensor"
    ]

    for col in important_columns:

        count = int(df[col].isna().sum())

        status = "PASS" if count == 0 else "FAIL"

        results.append({
            "validation_check": f"Missing values: {col}",
            "invalid_count": count,
            "status": status
        })

    invalid_mask = pd.Series(
        False,
        index=df.index
    )

    for mask in checks.values():
        invalid_mask |= mask

    invalid_observations = df.loc[
        invalid_mask
    ].copy()

    return pd.DataFrame(results), invalid_observations


# ==================================================
# DISTRIBUTION VALIDATION
# ==================================================

def validate_distribution(df):

    print("\n========== OBSERVATION DISTRIBUTION ==========\n")

    print("\nBy country:")
    print(df["country_name"].value_counts())

    print("\nBy year:")
    print(df["year"].value_counts().sort_index())

    print("\nBy sensor:")
    print(df["sensor"].value_counts())

    print("\nBy country, year and sensor:")

    distribution = (
        df.groupby(
            ["country_name", "year", "sensor"]
        )
        .size()
        .reset_index(name="observation_count")
    )

    print(distribution.to_string(index=False))

    return distribution


# ==================================================
# EXPORT VALIDATION RESULTS
# ==================================================

def export_results(df, summary, distribution, invalid):

    print("\n========== EXPORTING VALIDATION RESULTS ==========\n")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    summary.to_csv(
        OUTPUT_DIR / "harmonized_validation_summary.csv",
        index=False
    )

    distribution.to_csv(
        OUTPUT_DIR / "observations_by_group.csv",
        index=False
    )

    invalid.to_csv(
        OUTPUT_DIR / "invalid_observations.csv",
        index=False
    )

    print("Validation reports saved:")
    print(OUTPUT_DIR / "harmonized_validation_summary.csv")
    print(OUTPUT_DIR / "observations_by_group.csv")
    print(OUTPUT_DIR / "invalid_observations.csv")


# ==================================================
# MAIN
# ==================================================

def main():

    try:

        df = load_dataset()

        validate_columns(df)

        summary, invalid = validate_data(df)

        distribution = validate_distribution(df)

        export_results(
            df,
            summary,
            distribution,
            invalid
        )

        print("\n========== FINAL VALIDATION RESULT ==========\n")

        failed_checks = summary[
            summary["status"] == "FAIL"
        ]

        if len(failed_checks) == 0:

            print("ALL VALIDATION CHECKS PASSED!")

        else:

            print("VALIDATION ISSUES FOUND:")
            print(failed_checks.to_string(index=False))

        print("\nTotal observations:", len(df))
        print("Invalid observations:", len(invalid))

        print("\nVALIDATION COMPLETED!")

    except Exception as error:

        print("\nVALIDATION FAILED!")
        print("Reason:", error)

        sys.exit(1)


if __name__ == "__main__":
    main()
