
#!/usr/bin/env python3

"""
NASA FIRE DATA - FIRE EVENT GROUPING

Method:
    Graph connected components (Union-Find)

Inputs:
    data/validation/validated_matching_pairs.csv
    data/harmonized/combined_harmonized_fire_data.csv

Outputs:
    data/fire_events/fire_event_members.csv
    data/fire_events/fire_event_summary.csv
    data/fire_events/fire_event_validation.csv

Important:
    Events are candidate groups of connected detections.
    Only observations appearing in validated pairs are grouped.
    Unmatched detections remain in the harmonized dataset.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


# ==================================================
# CONFIGURATION
# ==================================================

PROJECT_DIR = Path(__file__).resolve().parent.parent

PAIRS_FILE = (
    PROJECT_DIR / "data" / "validation"
    / "validated_matching_pairs.csv"
)

HARMONIZED_FILE = (
    PROJECT_DIR / "data" / "harmonized"
    / "combined_harmonized_fire_data.csv"
)

OUTPUT_DIR = PROJECT_DIR / "data" / "fire_events"

MEMBERS_FILE = OUTPUT_DIR / "fire_event_members.csv"
SUMMARY_FILE = OUTPUT_DIR / "fire_event_summary.csv"
VALIDATION_FILE = OUTPUT_DIR / "fire_event_validation.csv"

MAX_PAIR_DISTANCE_METERS = 1000.0
MAX_PAIR_TIME_MINUTES = 30.0

EARTH_RADIUS_METERS = 6371008.8

# Used for flagging event-level extent, not rejecting events.
REVIEW_EVENT_SPAN_METERS = 1000.0
REVIEW_EVENT_DURATION_MINUTES = 30.0


# ==================================================
# UNION-FIND DATA STRUCTURE
# ==================================================

class UnionFind:

    def __init__(self):
        self.parent = {}
        self.size = {}

    def add(self, item):

        if item not in self.parent:
            self.parent[item] = item
            self.size[item] = 1

    def find(self, item):

        root = item

        while self.parent[root] != root:
            root = self.parent[root]

        while self.parent[item] != item:
            old_parent = self.parent[item]
            self.parent[item] = root
            item = old_parent

        return root

    def union(self, a, b):

        self.add(a)
        self.add(b)

        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.size[root_a] < self.size[root_b]:
            root_a, root_b = root_b, root_a

        self.parent[root_b] = root_a

        self.size[root_a] += self.size[root_b]


# ==================================================
# GEOGRAPHIC DISTANCE
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

    return (
        2 * EARTH_RADIUS_METERS
        * np.arcsin(np.sqrt(a))
    )


# ==================================================
# LOAD DATA
# ==================================================

def load_data():

    print("\n========== LOADING FIRE DATA ==========\n")

    for path in [PAIRS_FILE, HARMONIZED_FILE]:
        if not path.is_file():
            raise FileNotFoundError(path)

    pairs = pd.read_csv(
        PAIRS_FILE,
        dtype={
            "detection_id_a": "string",
            "detection_id_b": "string"
        }
    )

    harmonized = pd.read_csv(
        HARMONIZED_FILE,
        low_memory=False,
        dtype={"detection_id": "string"}
    )

    required_pairs = {
        "detection_id_a",
        "detection_id_b",
        "country_code",
        "year",
        "distance_meters",
        "time_difference_minutes"
    }

    required_obs = {
        "detection_id",
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "sensor",
        "country_name",
        "country_code",
        "year"
    }

    if required_pairs - set(pairs.columns):
        raise ValueError("Missing required pair columns")

    if required_obs - set(harmonized.columns):
        raise ValueError("Missing required observation columns")

    if harmonized["detection_id"].isna().any():
        raise ValueError("Missing observation IDs")

    if harmonized["detection_id"].duplicated().any():
        raise ValueError("Duplicate observation IDs")

    if pairs[["detection_id_a", "detection_id_b"]].isna().any().any():
        raise ValueError("Missing IDs in matching pairs")

    if pairs.empty:
        raise ValueError("No validated matching pairs found")

    harmonized["acq_datetime_utc"] = pd.to_datetime(
        harmonized["acq_datetime_utc"],
        utc=True,
        errors="raise"
    )

    for col in ["latitude", "longitude", "year"]:
        harmonized[col] = pd.to_numeric(
            harmonized[col],
            errors="raise"
        )

    pairs["year"] = pd.to_numeric(
        pairs["year"],
        errors="raise"
    )

    for col in ["distance_meters", "time_difference_minutes"]:
        pairs[col] = pd.to_numeric(
            pairs[col],
            errors="raise"
        )

    if (
        (~np.isfinite(pairs["distance_meters"])).any()
        or (pairs["distance_meters"] < 0).any()
        or (
            pairs["distance_meters"]
            > MAX_PAIR_DISTANCE_METERS + 1e-6
        ).any()
    ):
        raise ValueError("Pairs contain invalid distances")

    if (
        (~np.isfinite(pairs["time_difference_minutes"])).any()
        or (pairs["time_difference_minutes"] < 0).any()
        or (
            pairs["time_difference_minutes"]
            > MAX_PAIR_TIME_MINUTES + 1e-6
        ).any()
    ):
        raise ValueError("Pairs contain invalid time differences")

    print(f"Harmonized observations: {len(harmonized):,}")
    print(f"Validated pairs: {len(pairs):,}")

    return pairs, harmonized


# ==================================================
# BUILD FIRE EVENT GRAPH
# ==================================================

def build_graph(pairs):

    print("\n========== BUILDING FIRE EVENT GRAPH ==========\n")

    uf = UnionFind()

    for id_a, id_b in zip(
        pairs["detection_id_a"],
        pairs["detection_id_b"]
    ):
        if id_a == id_b:
            raise ValueError("Self-matching pair detected")

        uf.union(str(id_a), str(id_b))

    detection_ids = sorted(uf.parent.keys())

    print(f"Unique matched detections: {len(detection_ids):,}")

    membership = pd.DataFrame({
        "detection_id": detection_ids
    })

    membership["component_root"] = [
        uf.find(detection_id)
        for detection_id in detection_ids
    ]

    print(
        "Connected components:",
        f"{membership['component_root'].nunique():,}"
    )

    return membership


# ==================================================
# ATTACH ORIGINAL OBSERVATIONS
# ==================================================

def attach_observations(membership, harmonized):

    print("\n========== ATTACHING OBSERVATION DATA ==========\n")

    columns = [
        "detection_id",
        "sensor",
        "country_name",
        "country_code",
        "year",
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "frp"
    ]

    # FRP is optional in this stage
    if "frp" not in harmonized.columns:
        harmonized = harmonized.copy()
        harmonized["frp"] = np.nan

    members = membership.merge(
        harmonized[columns],
        on="detection_id",
        how="left",
        validate="one_to_one",
        indicator=True
    )

    if not members["_merge"].eq("both").all():
        raise ValueError("Unrecognized detection IDs found")

    members = members.drop(columns=["_merge"])

    if members[
        ["country_code", "year", "sensor", "acq_datetime_utc"]
    ].isna().any().any():
        raise ValueError("Missing required observation metadata")

    # Each graph component must remain in one country/year.
    component_check = members.groupby("component_root").agg(
        countries=("country_code", "nunique"),
        years=("year", "nunique")
    )

    if (
        (component_check["countries"] != 1).any()
        or (component_check["years"] != 1).any()
    ):
        raise ValueError(
            "A graph component crosses country/year boundaries"
        )

    return members


# ==================================================
# ASSIGN STABLE EVENT IDS
# ==================================================

def assign_event_ids(members):

    print("\n========== ASSIGNING FIRE EVENT IDS ==========\n")

    component_order = (
        members.groupby("component_root")
        .agg(
            country_code=("country_code", "first"),
            year=("year", "first"),
            start_time=("acq_datetime_utc", "min"),
            smallest_detection=("detection_id", "min")
        )
        .reset_index()
    )

    component_order = component_order.sort_values(
        [
            "country_code",
            "year",
            "start_time",
            "smallest_detection"
        ],
        kind="stable"
    ).reset_index(drop=True)

    component_order["event_number"] = (
        component_order.groupby(
            ["country_code", "year"]
        ).cumcount() + 1
    )

    component_order["fire_event_id"] = (
        component_order["country_code"].astype(str)
        + "_"
        + component_order["year"].astype(int).astype(str)
        + "_FIRE_"
        + component_order["event_number"]
        .astype(str).str.zfill(6)
    )

    members = members.merge(
        component_order[
            ["component_root", "fire_event_id"]
        ],
        on="component_root",
        how="left",
        validate="many_to_one"
    )

    if members["fire_event_id"].isna().any():
        raise ValueError("Some detections lack event IDs")

    print(
        f"Fire event groups created: "
        f"{members['fire_event_id'].nunique():,}"
    )

    return members


# ==================================================
# CHECK PAIR-TO-EVENT CONSISTENCY
# ==================================================

def validate_event_edges(pairs, members):

    print("\n========== VALIDATING EVENT CONNECTIONS ==========\n")

    event_lookup = members.set_index(
        "detection_id"
    )["fire_event_id"]

    event_a = pairs["detection_id_a"].map(event_lookup)
    event_b = pairs["detection_id_b"].map(event_lookup)

    if event_a.isna().any() or event_b.isna().any():
        raise ValueError("Matching pair has no event assignment")

    if not event_a.eq(event_b).all():
        raise ValueError(
            "Connected detection pair assigned to different events"
        )

    print("All validated edges belong to consistent events")


# ==================================================
# SUMMARIZE FIRE EVENTS
# ==================================================

def summarize_events(members, pairs):

    print("\n========== SUMMARIZING FIRE EVENTS ==========\n")

    members["frp"] = pd.to_numeric(
        members["frp"],
        errors="coerce"
    )

    summary = (
        members.groupby("fire_event_id")
        .agg(
            country_name=("country_name", "first"),
            country_code=("country_code", "first"),
            year=("year", "first"),
            detection_count=("detection_id", "size"),
            modis_count=("sensor", lambda x: (x == "MODIS").sum()),
            viirs_count=("sensor", lambda x: (x == "VIIRS").sum()),
            start_time_utc=("acq_datetime_utc", "min"),
            end_time_utc=("acq_datetime_utc", "max"),
            latitude_min=("latitude", "min"),
            latitude_max=("latitude", "max"),
            longitude_min=("longitude", "min"),
            longitude_max=("longitude", "max"),
            centroid_latitude=("latitude", "mean"),
            centroid_longitude=("longitude", "mean"),
            mean_frp=("frp", "mean"),
            max_frp=("frp", "max")
        )
        .reset_index()
    )

    summary["duration_minutes"] = (
        summary["end_time_utc"]
        - summary["start_time_utc"]
    ).dt.total_seconds() / 60.0

    # Approximate bounding-box diagonal (not exact
    # maximum pairwise separation).
    summary["bbox_diagonal_meters"] = haversine(
        summary["latitude_min"],
        summary["longitude_min"],
        summary["latitude_max"],
        summary["longitude_max"]
    )

    event_lookup = members.set_index(
        "detection_id"
    )["fire_event_id"]

    pair_events = pairs["detection_id_a"].map(
        event_lookup
    )

    pair_counts = pair_events.value_counts()

    summary["matching_pair_count"] = (
        summary["fire_event_id"]
        .map(pair_counts)
        .fillna(0)
        .astype(int)
    )

    summary["multi_sensor"] = (
        (summary["modis_count"] > 0)
        & (summary["viirs_count"] > 0)
    )

    summary["duration_review_flag"] = (
        summary["duration_minutes"]
        > REVIEW_EVENT_DURATION_MINUTES
    )

    summary["spatial_review_flag"] = (
        summary["bbox_diagonal_meters"]
        > REVIEW_EVENT_SPAN_METERS
    )

    summary["requires_review"] = (
        summary["duration_review_flag"]
        | summary["spatial_review_flag"]
    )

    return summary


# ==================================================
# EVENT VALIDATION REPORT
# ==================================================

def create_validation_report(members, summary, pairs):

    print("\n========== EVENT VALIDATION ==========\n")

    checks = {
        "Duplicate member IDs": int(
            members["detection_id"].duplicated().sum()
        ),
        "Missing event IDs": int(
            members["fire_event_id"].isna().sum()
        ),
        "Single-sensor events": int(
            (~summary["multi_sensor"]).sum()
        ),
        "Events exceeding review duration": int(
            summary["duration_review_flag"].sum()
        ),
        "Events exceeding review spatial extent": int(
            summary["spatial_review_flag"].sum()
        ),
        "Events requiring review": int(
            summary["requires_review"].sum()
        )
    }

    rows = []

    for name, count in checks.items():

        status = (
            "FAIL"
            if name in [
                "Duplicate member IDs",
                "Missing event IDs",
                "Single-sensor events"
            ] and count > 0
            else "REVIEW"
            if "review" in name.lower() and count > 0
            else "PASS"
        )

        rows.append({
            "validation_check": name,
            "count": count,
            "status": status
        })

        print(f"{name}: {count:,} [{status}]")

    # Overall graph consistency
    if len(members) != members["detection_id"].nunique():
        raise ValueError("Detections assigned to multiple events")

    if summary["matching_pair_count"].sum() != len(pairs):
        raise ValueError("Matching pair count mismatch")

    return pd.DataFrame(rows)


# ==================================================
# SAVE OUTPUTS
# ==================================================

def save_results(members, summary, validation):

    print("\n========== EXPORTING EVENT DATA ==========\n")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    member_columns = [
        "fire_event_id",
        "detection_id",
        "sensor",
        "country_name",
        "country_code",
        "year",
        "latitude",
        "longitude",
        "acq_datetime_utc",
        "frp"
    ]

    members[member_columns].sort_values(
        ["fire_event_id", "acq_datetime_utc", "detection_id"]
    ).to_csv(
        MEMBERS_FILE,
        index=False
    )

    summary.sort_values(
        ["country_code", "year", "start_time_utc", "fire_event_id"]
    ).to_csv(
        SUMMARY_FILE,
        index=False
    )

    validation.to_csv(
        VALIDATION_FILE,
        index=False
    )

    print("Saved:", MEMBERS_FILE)
    print("Saved:", SUMMARY_FILE)
    print("Saved:", VALIDATION_FILE)


# ==================================================
# FINAL SUMMARY
# ==================================================

def print_summary(members, summary, pairs, harmonized):

    print("\n========== FIRE EVENT GROUPING SUMMARY ==========\n")

    print(f"Total harmonized observations: {len(harmonized):,}")
    print(f"Validated matching pairs: {len(pairs):,}")
    print(f"Matched unique detections: {len(members):,}")

    print(
        "Unmatched observations:",
        f"{len(harmonized) - len(members):,}"
    )

    print(
        "Candidate fire events:",
        f"{len(summary):,}"
    )

    print(
        "Events requiring review:",
        f"{summary['requires_review'].sum():,}"
    )

    print("\nEvents by country and year:")

    print(
        summary.groupby(
            ["country_name", "year"]
        ).size().to_string()
    )

    print("\nFIRE EVENT GROUPING COMPLETED!")


# ==================================================
# MAIN
# ==================================================

def main():

    try:

        pairs, harmonized = load_data()

        membership = build_graph(pairs)

        members = attach_observations(
            membership,
            harmonized
        )

        members = assign_event_ids(members)

        validate_event_edges(pairs, members)

        summary = summarize_events(members, pairs)

        validation = create_validation_report(
            members,
            summary,
            pairs
        )

        save_results(
            members,
            summary,
            validation
        )

        print_summary(
            members,
            summary,
            pairs,
            harmonized
        )

    except Exception as error:

        print("\nFIRE EVENT GROUPING FAILED!")
        print("Reason:", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
