
#!/usr/bin/env python3

"""
NASA FIRE DATA - MATCHING VALIDATION AND CORRECTION

Inputs:
    data/harmonized/combined_harmonized_fire_data.csv
    data/overlap_detection/overlap_pairs.csv

Outputs:
    data/validation/validated_matching_pairs.csv
    data/validation/invalid_matching_pairs.csv
    data/validation/matching_validation_summary.csv
    data/validation/matching_distribution.csv

This script:
    - Recalculates actual geographic distances.
    - Recalculates actual time differences in minutes.
    - Validates detection IDs, sensors, countries, and years.
    - Detects duplicate matching pairs.
    - Excludes invalid pairs from the validated output.
    - Preserves original input files.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

HARMONIZED_FILE = (
    PROJECT_DIR / "data" / "harmonized"
    / "combined_harmonized_fire_data.csv"
)

MATCHING_FILE = (
    PROJECT_DIR / "data" / "overlap_detection"
    / "overlap_pairs.csv"
)

OUTPUT_DIR = PROJECT_DIR / "data" / "validation"

DISTANCE_THRESHOLD_METERS = 1000.0
TIME_THRESHOLD_MINUTES = 30.0
EARTH_RADIUS_METERS = 6371000.0

# Tolerance for numerical rounding
EPSILON = 1e-6


# ==================================================
# HAVERSINE DISTANCE
# ==================================================

def haversine(lat1, lon1, lat2, lon2):

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    a = np.clip(a, 0, 1)

    return 2 * EARTH_RADIUS_METERS * np.arcsin(np.sqrt(a))


# ==================================================
# LOAD DATA
# ==================================================

def load_data():

    print("\n========== LOADING DATA ==========\n")

    for path in [HARMONIZED_FILE, MATCHING_FILE]:
        if not path.is_file():
            raise FileNotFoundError(path)

    harmonized = pd.read_csv(
        HARMONIZED_FILE,
        low_memory=False,
        dtype={"detection_id": "string"}
    )

    pairs = pd.read_csv(
        MATCHING_FILE,
        dtype={
            "detection_id_a": "string",
            "detection_id_b": "string"
        }
    )

    required_h = {
        "detection_id", "latitude", "longitude",
        "acq_datetime_utc", "sensor",
        "country_name", "country_code", "year"
    }

    required_p = {
        "detection_id_a", "detection_id_b",
        "sensor_a", "sensor_b",
        "country_name", "country_code", "year",
        "distance_meters", "time_difference_minutes",
        "spatial_match", "temporal_match"
    }

    if required_h - set(harmonized.columns):
        raise ValueError(
            f"Missing harmonized columns: "
            f"{required_h - set(harmonized.columns)}"
        )

    if required_p - set(pairs.columns):
        raise ValueError(
            f"Missing matching columns: "
            f"{required_p - set(pairs.columns)}"
        )

    if harmonized["detection_id"].isna().any():
        raise ValueError("Harmonized data contains missing IDs")

    if harmonized["detection_id"].duplicated().any():
        raise ValueError("Harmonized data contains duplicate IDs")

    print(f"Harmonized observations: {len(harmonized):,}")
    print(f"Original matching pairs: {len(pairs):,}")

    return harmonized, pairs


# ==================================================
# PREPARE ORIGINAL OBSERVATIONS
# ==================================================

def prepare_observations(harmonized):

    columns = [
        "detection_id",
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "sensor",
        "country_name",
        "country_code",
        "year"
    ]

    observations = harmonized[columns].copy()

    for column in ["latitude", "longitude", "year"]:
        observations[column] = pd.to_numeric(
            observations[column],
            errors="coerce"
        )

    observations["acq_datetime_utc"] = pd.to_datetime(
        observations["acq_datetime_utc"],
        utc=True,
        errors="coerce"
    )

    return observations


# ==================================================
# LINK MATCHED DETECTIONS
# ==================================================

def attach_observations(observations, pairs):

    print("\n========== LINKING OBSERVATIONS ==========\n")

    a = observations.add_prefix("a_")
    b = observations.add_prefix("b_")

    df = pairs.merge(
        a,
        left_on="detection_id_a",
        right_on="a_detection_id",
        how="left",
        validate="many_to_one"
    )

    df = df.merge(
        b,
        left_on="detection_id_b",
        right_on="b_detection_id",
        how="left",
        validate="many_to_one"
    )

    return df


# ==================================================
# RECALCULATE ACTUAL VALUES
# ==================================================

def recalculate(df):

    print("\n========== RECALCULATING MATCHES ==========\n")

    coordinate_columns = [
        "a_latitude", "a_longitude",
        "b_latitude", "b_longitude"
    ]

    for column in coordinate_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df["actual_distance_meters"] = haversine(
        df["a_latitude"].to_numpy(dtype=float),
        df["a_longitude"].to_numpy(dtype=float),
        df["b_latitude"].to_numpy(dtype=float),
        df["b_longitude"].to_numpy(dtype=float)
    )

    # Correct time calculation:
    # Timedelta -> seconds -> minutes
    df["actual_time_difference_minutes"] = (
        df["a_acq_datetime_utc"]
        - df["b_acq_datetime_utc"]
    ).abs().dt.total_seconds() / 60.0

    return df


# ==================================================
# VALIDATE MATCHING PAIRS
# ==================================================

def validate_pairs(df):

    print("\n========== VALIDATING MATCHING PAIRS ==========\n")

    checks = {}

    checks["Missing detection A"] = (
        df["a_detection_id"].isna()
    )

    checks["Missing detection B"] = (
        df["b_detection_id"].isna()
    )

    checks["Self matching"] = (
        df["detection_id_a"]
        .eq(df["detection_id_b"])
        .fillna(False)
    )

    # Order-independent duplicate pair detection
    a = df["detection_id_a"].fillna("").astype(str)
    b = df["detection_id_b"].fillna("").astype(str)

    key = np.where(
        a <= b,
        a + "|" + b,
        b + "|" + a
    )

    # Retain first occurrence; exclude repeated copies
    checks["Duplicate pairs"] = pd.Series(
        key,
        index=df.index
    ).duplicated(keep="first")

    # Check sensor combinations using original data
    actual_a = df["a_sensor"].astype("string").str.upper()
    actual_b = df["b_sensor"].astype("string").str.upper()

    valid_sensor = (
        ((actual_a == "MODIS") & (actual_b == "VIIRS"))
        |
        ((actual_a == "VIIRS") & (actual_b == "MODIS"))
    ).fillna(False)

    checks["Invalid sensor combination"] = ~valid_sensor

    checks["Sensor metadata mismatch"] = ~(
        df["sensor_a"].astype("string").str.upper().eq(actual_a)
        & df["sensor_b"].astype("string").str.upper().eq(actual_b)
    ).fillna(False)

    # Country checks
    checks["Country mismatch"] = ~(
        df["a_country_name"].eq(df["country_name"])
        & df["b_country_name"].eq(df["country_name"])
        & df["a_country_name"].eq(df["b_country_name"])
    ).fillna(False)

    checks["Country code mismatch"] = ~(
        df["a_country_code"].eq(df["country_code"])
        & df["b_country_code"].eq(df["country_code"])
    ).fillna(False)

    # Year checks
    checks["Year mismatch"] = ~(
        df["a_year"].eq(df["year"])
        & df["b_year"].eq(df["year"])
    ).fillna(False)

    # Actual geographic distance
    distance = df["actual_distance_meters"]

    checks["Invalid actual distance"] = (
        distance.isna()
        | ~np.isfinite(distance)
        | (distance < 0)
        | (distance > DISTANCE_THRESHOLD_METERS + EPSILON)
    )

    # Actual time difference
    time = df["actual_time_difference_minutes"]

    checks["Invalid actual time difference"] = (
        time.isna()
        | ~np.isfinite(time)
        | (time < 0)
        | (time > TIME_THRESHOLD_MINUTES + EPSILON)
    )

    # Report stored-value discrepancies separately
    stored_distance = pd.to_numeric(
        df["distance_meters"],
        errors="coerce"
    )

    stored_time = pd.to_numeric(
        df["time_difference_minutes"],
        errors="coerce"
    )

    distance_discrepancies = (
        stored_distance - distance
    ).abs() > 5.0

    time_discrepancies = (
        stored_time - time
    ).abs() > 0.01

    # Build validation results
    summary = []
    invalid_mask = pd.Series(False, index=df.index)

    for name, mask in checks.items():

        mask = mask.fillna(True).astype(bool)

        count = int(mask.sum())
        invalid_mask |= mask

        status = "PASS" if count == 0 else "FAIL"

        summary.append({
            "validation_check": name,
            "invalid_count": count,
            "status": status
        })

        print(f"{name}: {count:,} [{status}]")

    print("\nStored distance discrepancies:",
          int(distance_discrepancies.sum()))

    print("Stored time discrepancies:",
          int(time_discrepancies.sum()))

    # Validity depends on recomputed actual values,
    # not on incorrect stored time values.
    valid = df.loc[~invalid_mask].copy()
    invalid = df.loc[invalid_mask].copy()

    # Replace old calculated fields with correct values
    valid["distance_meters"] = (
        valid["actual_distance_meters"]
    )

    valid["time_difference_minutes"] = (
        valid["actual_time_difference_minutes"]
    )

    valid["spatial_match"] = True
    valid["temporal_match"] = True

    # Select original matching output schema
    output_columns = [
        "detection_id_a",
        "detection_id_b",
        "sensor_a",
        "sensor_b",
        "country_name",
        "country_code",
        "year",
        "distance_meters",
        "time_difference_minutes",
        "spatial_match",
        "temporal_match"
    ]

    valid_output = valid[output_columns].copy()

    invalid_output = invalid[
        output_columns
    ].copy()

    invalid_output["actual_distance_meters"] = (
        invalid["actual_distance_meters"]
    )

    invalid_output["actual_time_difference_minutes"] = (
        invalid["actual_time_difference_minutes"]
    )

    # Add stored-value discrepancy statistics
    summary.extend([
        {
            "validation_check": "Stored distance discrepancies",
            "invalid_count": int(distance_discrepancies.sum()),
            "status": "WARNING"
        },
        {
            "validation_check": "Stored time discrepancies",
            "invalid_count": int(time_discrepancies.sum()),
            "status": "WARNING"
        }
    ])

    return valid_output, invalid_output, pd.DataFrame(summary)


# ==================================================
# EXPORT REPORTS
# ==================================================

def export_results(valid, invalid, summary):

    print("\n========== EXPORTING RESULTS ==========\n")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    valid.to_csv(
        OUTPUT_DIR / "validated_matching_pairs.csv",
        index=False
    )

    invalid.to_csv(
        OUTPUT_DIR / "invalid_matching_pairs.csv",
        index=False
    )

    summary.to_csv(
        OUTPUT_DIR / "matching_validation_summary.csv",
        index=False
    )

    distribution = (
        valid.groupby(
            ["country_name", "year", "sensor_a", "sensor_b"]
        )
        .size()
        .reset_index(name="matching_pairs")
    )

    distribution.to_csv(
        OUTPUT_DIR / "matching_distribution.csv",
        index=False
    )

    print(f"Valid matching pairs: {len(valid):,}")
    print(f"Excluded matching pairs: {len(invalid):,}")

    print("\nOutput directory:", OUTPUT_DIR)


# ==================================================
# MAIN
# ==================================================

def main():

    try:

        harmonized, pairs = load_data()

        observations = prepare_observations(
            harmonized
        )

        validated = attach_observations(
            observations,
            pairs
        )

        validated = recalculate(
            validated
        )

        valid, invalid, summary = validate_pairs(
            validated
        )

        export_results(
            valid,
            invalid,
            summary
        )

        print("\n========== FINAL RESULT ==========\n")

        print("Original pairs:", len(pairs))
        print("Validated pairs:", len(valid))
        print("Excluded pairs:", len(invalid))

        if invalid.empty:
            print("\nALL MATCHING PAIRS PASSED VALIDATION!")
        else:
            print(
                "\nSome matching pairs were excluded. "
                "Review the validation reports."
            )

        print("\nVALIDATION COMPLETED!")

    except Exception as error:

        print("\nVALIDATION FAILED!")
        print("Reason:", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
