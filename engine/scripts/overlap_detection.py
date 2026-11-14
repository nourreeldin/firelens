
#!/usr/bin/env python3

"""
NASA FIRE DATA - CORRECTED SPATIAL-TEMPORAL MATCHING

Countries:
    South Africa, Egypt, Algeria

Years:
    2018, 2019, 2020

Sensors:
    MODIS and VIIRS

Thresholds:
    Spatial: 1000 meters
    Temporal: 30 minutes

Input:
    data/harmonized/combined_harmonized_fire_data.csv

Outputs:
    data/overlap_detection/overlap_pairs.csv
    data/overlap_detection/matching_summary.csv

Fix:
    Explicit nanosecond timestamp conversion.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd

try:
    from scipy.spatial import cKDTree
except ImportError:
    print("Install SciPy: python -m pip install scipy")
    sys.exit(1)


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_DIR / "data" / "harmonized"
    / "combined_harmonized_fire_data.csv"
)

OUTPUT_DIR = PROJECT_DIR / "data" / "overlap_detection"

PAIRS_FILE = OUTPUT_DIR / "overlap_pairs.csv"
SUMMARY_FILE = OUTPUT_DIR / "matching_summary.csv"

MAX_DISTANCE_METERS = 1000.0
MAX_TIME_DIFFERENCE_MINUTES = 30.0

EARTH_RADIUS_METERS = 6371008.8

NANOSECONDS_PER_MINUTE = 60_000_000_000

TIME_THRESHOLD_NS = int(
    MAX_TIME_DIFFERENCE_MINUTES
    * NANOSECONDS_PER_MINUTE
)

BATCH_SIZE = 5000

OUTPUT_COLUMNS = [
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


# ==================================================
# LOAD DATA
# ==================================================

def load_dataset():

    print("\n========== LOADING HARMONIZED DATA ==========\n")

    if not INPUT_FILE.exists():
        raise FileNotFoundError(INPUT_FILE)

    df = pd.read_csv(
        INPUT_FILE,
        dtype={"detection_id": "string"},
        low_memory=False
    )

    required = [
        "detection_id",
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "country_name",
        "country_code",
        "year",
        "sensor"
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df["latitude"] = pd.to_numeric(
        df["latitude"], errors="raise"
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"], errors="raise"
    )

    df["acq_datetime_utc"] = pd.to_datetime(
        df["acq_datetime_utc"],
        utc=True,
        errors="raise"
    )

    df["year"] = pd.to_numeric(
        df["year"],
        errors="raise"
    ).astype(int)

    df["sensor"] = (
        df["sensor"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    if df["detection_id"].isna().any():
        raise ValueError("Missing detection IDs")

    if df["detection_id"].duplicated().any():
        raise ValueError("Duplicate detection IDs")

    if not df["sensor"].isin(["MODIS", "VIIRS"]).all():
        raise ValueError("Unexpected sensor detected")

    if df["acq_datetime_utc"].isna().any():
        raise ValueError("Invalid timestamps")

    valid_coordinates = (
        df["latitude"].between(-90, 90)
        & df["longitude"].between(-180, 180)
        & np.isfinite(df["latitude"])
        & np.isfinite(df["longitude"])
    )

    if not valid_coordinates.all():
        raise ValueError("Invalid coordinates detected")

    print(f"Observations loaded: {len(df):,}")

    print("\nSensor distribution:")
    print(df["sensor"].value_counts())

    return df


# ==================================================
# CORRECT TIMESTAMP CONVERSION
# ==================================================

def timestamps_to_nanoseconds(series):

    """
    Convert UTC timestamps explicitly to datetime64[ns].

    Avoid relying on .astype('int64') directly
    because the original datetime unit may be
    microseconds rather than nanoseconds.
    """

    timestamps = pd.to_datetime(
        series,
        utc=True,
        errors="raise"
    )

    if timestamps.isna().any():
        raise ValueError("Missing timestamps")

    # UTC-aware -> UTC-naive -> explicit nanoseconds
    timestamps_ns = (
        timestamps
        .dt.tz_localize(None)
        .to_numpy(dtype="datetime64[ns]")
        .astype(np.int64)
    )

    return timestamps_ns


# ==================================================
# COORDINATES TO 3D UNIT SPHERE
# ==================================================

def coordinates_to_xyz(latitude, longitude):

    lat = np.radians(
        np.asarray(latitude, dtype=float)
    )

    lon = np.radians(
        np.asarray(longitude, dtype=float)
    )

    x = np.cos(lat) * np.cos(lon)
    y = np.cos(lat) * np.sin(lon)
    z = np.sin(lat)

    return np.column_stack((x, y, z))


# ==================================================
# HAVERSINE DISTANCE
# ==================================================

def haversine_distance(lat1, lon1, lat2, lon2):

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

    return (
        2 * EARTH_RADIUS_METERS
        * np.arcsin(np.sqrt(a))
    )


# ==================================================
# MATCH COUNTRY/YEAR
# ==================================================

def match_group(group, output_handle, summary_rows):

    country = group["country_name"].iloc[0]
    year = int(group["year"].iloc[0])

    modis = (
        group[group["sensor"] == "MODIS"]
        .reset_index(drop=True)
    )

    viirs = (
        group[group["sensor"] == "VIIRS"]
        .reset_index(drop=True)
    )

    print(
        f"\nProcessing {country} {year}: "
        f"MODIS={len(modis):,}, VIIRS={len(viirs):,}"
    )

    total_pairs = 0

    if not modis.empty and not viirs.empty:

        # Build spatial search tree
        viirs_xyz = coordinates_to_xyz(
            viirs["latitude"].to_numpy(),
            viirs["longitude"].to_numpy()
        )

        tree = cKDTree(viirs_xyz)

        angular_radius = (
            MAX_DISTANCE_METERS / EARTH_RADIUS_METERS
        )

        chord_radius = (
            2 * np.sin(angular_radius / 2)
        )

        # FIX: explicitly convert to nanoseconds
        modis_times = timestamps_to_nanoseconds(
            modis["acq_datetime_utc"]
        )

        viirs_times = timestamps_to_nanoseconds(
            viirs["acq_datetime_utc"]
        )

        modis_lat = modis["latitude"].to_numpy()
        modis_lon = modis["longitude"].to_numpy()

        viirs_lat = viirs["latitude"].to_numpy()
        viirs_lon = viirs["longitude"].to_numpy()

        modis_ids = modis["detection_id"].to_numpy()
        viirs_ids = viirs["detection_id"].to_numpy()

        country_code = group["country_code"].iloc[0]

        for start in range(0, len(modis), BATCH_SIZE):

            end = min(
                start + BATCH_SIZE,
                len(modis)
            )

            batch_xyz = coordinates_to_xyz(
                modis_lat[start:end],
                modis_lon[start:end]
            )

            candidates = tree.query_ball_point(
                batch_xyz,
                r=chord_radius
            )

            batch_records = []

            for local_pos, positions in enumerate(candidates):

                if not positions:
                    continue

                m = start + local_pos

                positions = np.asarray(
                    positions,
                    dtype=np.int64
                )

                # Correct time difference in nanoseconds
                differences_ns = np.abs(
                    viirs_times[positions] - modis_times[m]
                )

                # Apply actual 30-minute threshold
                time_mask = (
                    differences_ns <= TIME_THRESHOLD_NS
                )

                positions = positions[time_mask]
                differences_ns = differences_ns[time_mask]

                if positions.size == 0:
                    continue

                distances = haversine_distance(
                    modis_lat[m],
                    modis_lon[m],
                    viirs_lat[positions],
                    viirs_lon[positions]
                )

                distance_mask = (
                    distances <= MAX_DISTANCE_METERS
                )

                positions = positions[distance_mask]
                differences_ns = differences_ns[distance_mask]
                distances = distances[distance_mask]

                if positions.size == 0:
                    continue

                # Convert nanoseconds to minutes
                differences_minutes = (
                    differences_ns / NANOSECONDS_PER_MINUTE
                )

                for j, v in enumerate(positions):

                    batch_records.append({
                        "detection_id_a": modis_ids[m],
                        "detection_id_b": viirs_ids[v],
                        "sensor_a": "MODIS",
                        "sensor_b": "VIIRS",
                        "country_name": country,
                        "country_code": country_code,
                        "year": year,
                        "distance_meters": float(distances[j]),
                        "time_difference_minutes": float(
                            differences_minutes[j]
                        ),
                        "spatial_match": True,
                        "temporal_match": True
                    })

            if batch_records:

                pd.DataFrame(
                    batch_records,
                    columns=OUTPUT_COLUMNS
                ).to_csv(
                    output_handle,
                    index=False,
                    header=False
                )

                total_pairs += len(batch_records)

            print(
                f"Processed MODIS: {end:,}/{len(modis):,} "
                f"| Pairs: {total_pairs:,}",
                end="\r"
            )

    print()
    print(f"Matching pairs found: {total_pairs:,}")

    summary_rows.append({
        "country_name": country,
        "year": year,
        "modis_observations": len(modis),
        "viirs_observations": len(viirs),
        "matching_pairs": total_pairs
    })


# ==================================================
# RUN MATCHING
# ==================================================

def run_matching(df):

    print("\n========== SPATIAL-TEMPORAL MATCHING ==========\n")

    print(
        f"Distance threshold: {MAX_DISTANCE_METERS} meters"
    )

    print(
        f"Time threshold: {MAX_TIME_DIFFERENCE_MINUTES} minutes"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    summary_rows = []

    # Write to a temporary file first.
    # Preserve the previous output if matching fails.
    temp_pairs_file = PAIRS_FILE.with_suffix(".csv.tmp")
    temp_summary_file = SUMMARY_FILE.with_suffix(".csv.tmp")

    try:

        with open(
            temp_pairs_file,
            "w",
            encoding="utf-8"
        ) as output_handle:

            pd.DataFrame(
                columns=OUTPUT_COLUMNS
            ).to_csv(
                output_handle,
                index=False
            )

            grouped = df.groupby(
                ["country_code", "year"],
                sort=True
            )

            for _, group in grouped:

                match_group(
                    group,
                    output_handle,
                    summary_rows
                )

        summary = pd.DataFrame(summary_rows)

        summary.to_csv(
            temp_summary_file,
            index=False
        )

        # Publish the completed outputs
        temp_pairs_file.replace(PAIRS_FILE)
        temp_summary_file.replace(SUMMARY_FILE)

    finally:
        temp_pairs_file.unlink(missing_ok=True)
        temp_summary_file.unlink(missing_ok=True)

    print("\n========== MATCHING SUMMARY ==========\n")

    print(summary.to_string(index=False))

    print(
        "\nTotal matching pairs:",
        f"{summary['matching_pairs'].sum():,}"
    )

    print("\nPairs saved to:")
    print(PAIRS_FILE)

    print("\nSummary saved to:")
    print(SUMMARY_FILE)


# ==================================================
# MAIN
# ==================================================

def main():

    try:

        df = load_dataset()

        run_matching(df)

        print("\nMATCHING COMPLETED SUCCESSFULLY!")

    except Exception as error:

        print("\nMATCHING FAILED!")
        print("Reason:", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
