
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
from pathlib import Path

# Always use paths relative to this Python file.
PROJECT_FOLDER = Path(__file__).resolve().parent


# ==========================================
# 1. LOAD DATASET
# ==========================================

csv_file = PROJECT_FOLDER / "modis_2018_South_Africa.csv"

if not csv_file.exists():
    raise FileNotFoundError(f"Dataset file not found: {csv_file}")

df = pd.read_csv(csv_file)

print("\n========== DATASET INFORMATION ==========")

print("\nFirst 5 Rows:")
print(df.head())

print("\nOriginal Dataset Shape:", df.shape)

print("\nDataset Information:")
df.info()

required_columns = [
    "latitude", "longitude", "brightness",
    "scan", "track", "acq_date", "acq_time",
    "satellite", "instrument", "confidence",
    "version", "bright_t31", "frp",
    "daynight", "type"
]

missing_columns = [
    col for col in required_columns if col not in df.columns
]

if missing_columns:
    raise ValueError(f"Missing required columns: {missing_columns}")


# ==========================================
# 2. DATA CLEANING
# ==========================================

print("\n========== DATA CLEANING ==========")

numeric_cols = [
    "latitude", "longitude", "brightness",
    "bright_t31", "scan", "track",
    "acq_time", "confidence", "frp",
    "type", "version"
]

for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# Remove records where type = 2.
print("\n========== TYPE FILTERING ==========")

print("Records with Type = 2:", (df["type"] == 2).sum())

df = df[df["type"] != 2].copy()

print("Shape After Removing Type 2:", df.shape)

print("\nRemaining Fire Types:")
print(df["type"].value_counts(dropna=False))


print("\nMissing Values Before Cleaning:")
print(df.isnull().sum())

print("\nTotal Missing Values:", df.isnull().sum().sum())

# Remove exact duplicate rows.
print("\nDuplicate Rows:", df.duplicated().sum())

df = df.drop_duplicates().copy()

print("Shape After Removing Duplicates:", df.shape)


# Check invalid coordinates and FRP.
invalid_latitude = (
    (df["latitude"] < -90) | (df["latitude"] > 90)
)

invalid_longitude = (
    (df["longitude"] < -180) | (df["longitude"] > 180)
)

print("\nInvalid Latitude:", invalid_latitude.sum())
print("Invalid Longitude:", invalid_longitude.sum())

print("Negative FRP:", (df["frp"] < 0).sum())
print("Zero FRP:", (df["frp"] == 0).sum())

# Zero FRP records are retained for investigation.
print("\nRecords with FRP = 0:")
print(df[df["frp"] == 0])

print("\nMissing Essential Records:")
print("Missing Latitude:", df["latitude"].isna().sum())
print("Missing Longitude:", df["longitude"].isna().sum())
print("Missing Date:", df["acq_date"].isna().sum())
print("Missing Time:", df["acq_time"].isna().sum())
print("Missing FRP:", df["frp"].isna().sum())


# ==========================================
# 3. TEMPORAL ALIGNMENT
# ==========================================

print("\n========== TEMPORAL ALIGNMENT ==========")

df["acq_date"] = pd.to_datetime(
    df["acq_date"], errors="coerce"
)

# NASA acquisition time is HHMM in UTC.
valid_numeric_time = (
    df["acq_time"].notna()
    & (df["acq_time"] % 1 == 0)
    & (df["acq_time"] >= 0)
    & (df["acq_time"] <= 2359)
)

time_string = pd.Series(
    pd.NA, index=df.index, dtype="string"
)

time_string.loc[valid_numeric_time] = (
    df.loc[valid_numeric_time, "acq_time"]
    .astype(int)
    .astype(str)
    .str.zfill(4)
)

df["hour"] = pd.to_numeric(
    time_string.str[:2], errors="coerce"
)

df["minute"] = pd.to_numeric(
    time_string.str[2:], errors="coerce"
)

invalid_time = (
    df["hour"].isna()
    | df["minute"].isna()
    | (df["hour"] > 23)
    | (df["minute"] > 59)
)

print("\nInvalid Acquisition Times:", invalid_time.sum())

df["acq_datetime_utc"] = pd.to_datetime(
    df["acq_date"].dt.strftime("%Y-%m-%d")
    + " "
    + time_string,
    format="%Y-%m-%d %H%M",
    errors="coerce",
    utc=True
)

print("\nFirst 5 UTC Timestamps:")
print(df["acq_datetime_utc"].head())

print("\nDate Coverage:")
print("First Date:", df["acq_datetime_utc"].min())
print("Last Date:", df["acq_datetime_utc"].max())

print(
    "\nNumber of Unique Acquisition Dates:",
    df["acq_date"].nunique()
)

df["year"] = df["acq_datetime_utc"].dt.year
df["month"] = df["acq_datetime_utc"].dt.month
df["day"] = df["acq_datetime_utc"].dt.day

df["day_of_year"] = (
    df["acq_datetime_utc"].dt.day_of_year
)


# ==========================================
# 4. SPATIAL ALIGNMENT
# ==========================================

print("\n========== SPATIAL ALIGNMENT ==========")

# Standardize coordinate precision to 5 decimal places.
df["latitude"] = df["latitude"].round(5)
df["longitude"] = df["longitude"].round(5)

# WGS84 geographic coordinate reference system.
df["coordinate_reference_system"] = "EPSG:4326"

print("\nCoordinate Reference System: WGS84 (EPSG:4326)")

print("\nLatitude Range:")
print("Minimum:", df["latitude"].min())
print("Maximum:", df["latitude"].max())

print("\nLongitude Range:")
print("Minimum:", df["longitude"].min())
print("Maximum:", df["longitude"].max())

repeated_coordinates = df.duplicated(
    subset=["latitude", "longitude"]
).sum()

print("\nRepeated Coordinate Pairs:", repeated_coordinates)

# Create 0.1-degree geographical grid cells.
GRID_SIZE = 0.1

df["grid_lat"] = np.floor(
    (df["latitude"] + 90) / GRID_SIZE
).astype("Int64")

df["grid_lon"] = np.floor(
    (df["longitude"] + 180) / GRID_SIZE
).astype("Int64")

df["spatial_grid_id"] = (
    df["grid_lat"].astype("string")
    + "_"
    + df["grid_lon"].astype("string")
)

print("\nNumber of Unique Spatial Grid Cells:")
print(df["spatial_grid_id"].nunique())

print("\nSample Spatial Grid IDs:")
print(
    df[["latitude", "longitude", "spatial_grid_id"]].head()
)


# ==========================================
# 5. HANDLE INVALID RECORDS
# ==========================================

print("\n========== INVALID RECORD HANDLING ==========")

# Remove records that cannot be located or timed,
# and records with missing or negative FRP.
# Keep zero FRP records.

invalid_records = (
    df["latitude"].isna()
    | df["longitude"].isna()
    | (df["latitude"] < -90)
    | (df["latitude"] > 90)
    | (df["longitude"] < -180)
    | (df["longitude"] > 180)
    | df["acq_datetime_utc"].isna()
    | df["frp"].isna()
    | (df["frp"] < 0)
)

print("Invalid Records to Remove:", invalid_records.sum())

df = df.loc[~invalid_records].copy()

print("Shape After Invalid Record Removal:", df.shape)


# ==========================================
# 6. COUNTRY ASSIGNMENT USING REAL BOUNDARIES
# ==========================================

print("\n========== COUNTRY ASSIGNMENT ==========")

boundary_file = (
    PROJECT_FOLDER
    / "ne_50m_admin_0_countries"
    / "ne_50m_admin_0_countries_lakes.shp"
)

print("\nLooking for country boundary file at:", boundary_file)
print("Country boundary file exists:", boundary_file.exists())

if not boundary_file.exists():
    raise FileNotFoundError(
        f"Country boundary file not found: {boundary_file}\n"
        "Make sure the folder 'ne_50m_admin_0_countries' "
        "is beside your Python file and contains "
        "'ne_50m_admin_0_countries_lakes.shp'."
    )

world = gpd.read_file(boundary_file)

if world.crs is None:
    raise ValueError(
        "The country boundary file has no CRS information. "
        "Make sure the extracted .prj file is present."
    )

required_boundary_columns = [
    "ADMIN", "ISO_A3", "CONTINENT", "geometry"
]

missing_boundary_columns = [
    col for col in required_boundary_columns
    if col not in world.columns
]

if missing_boundary_columns:
    raise ValueError(
        f"Missing expected boundary columns: {missing_boundary_columns}"
    )

world = world[required_boundary_columns].copy()

world = world.rename(columns={
    "ADMIN": "country_name",
    "ISO_A3": "country_code",
    "CONTINENT": "continent"
})

fire_points = gpd.GeoDataFrame(
    df.copy(),
    geometry=gpd.points_from_xy(
        df["longitude"],
        df["latitude"]
    ),
    crs="EPSG:4326"
)

world = world.to_crs(fire_points.crs)

joined = gpd.sjoin(
    fire_points,
    world[[
        "country_name",
        "country_code",
        "continent",
        "geometry"
    ]],
    how="left",
    predicate="within"
)

# Keep one match per original record if polygons overlap.
joined = joined[
    ~joined.index.duplicated(keep="first")
]

df["country_name"] = joined["country_name"].reindex(df.index)
df["country_code"] = joined["country_code"].reindex(df.index)
df["continent"] = joined["continent"].reindex(df.index)

print("\nFirst 10 Country Assignments:")

print(df[[
    "latitude",
    "longitude",
    "country_name",
    "country_code",
    "continent",
    "spatial_grid_id"
]].head(10))

print("\nNumber of Unique Countries Before Removing Unmatched Records:")
print(df["country_name"].nunique())

print("\nFire Detections Per Country (Top 20, Before Removal):")
print(df["country_name"].value_counts().head(20))

matched_before = df["country_name"].notna().sum()
unmatched_before = df["country_name"].isna().sum()

print("\nRecords Matched to a Country:", matched_before)
print("Records Not Matched to a Country:", unmatched_before)


# ==========================================
# 7. REMOVE UNMATCHED COUNTRY RECORDS
# ==========================================

print("\n========== REMOVING UNMATCHED COUNTRY RECORDS ==========")

records_before_country_filter = len(df)

df = df.dropna(
    subset=["country_name", "country_code", "continent"]
).copy()

removed_unmatched_records = (
    records_before_country_filter - len(df)
)

print("Records Before Country Filtering:", records_before_country_filter)
print("Unmatched Records Removed:", removed_unmatched_records)
print("Records Remaining:", len(df))

remaining_unmatched = df[
    ["country_name", "country_code", "continent"]
].isna().any(axis=1).sum()

print("Unmatched Records Remaining:", remaining_unmatched)


# ==========================================
# 8. STATISTICAL ANALYSIS
# ==========================================

print("\n========== STATISTICAL SUMMARY ==========")

print(df.describe())

print("\nSatellite Distribution:")
print(df["satellite"].value_counts(dropna=False))

print("\nConfidence Distribution:")
print(df["confidence"].value_counts(dropna=False))

print("\nDay/Night Distribution:")
print(df["daynight"].value_counts(dropna=False))


# ==========================================
# 9. OUTLIER DETECTION
# ==========================================

print("\n========== OUTLIER DETECTION ==========")

numerical_cols = df.select_dtypes(
    include=np.number
).columns

for col in numerical_cols:

    Q1 = df[col].quantile(0.25)
    Q3 = df[col].quantile(0.75)

    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR

    outliers = (
        (df[col] < lower) | (df[col] > upper)
    ).sum()

    print(f"{col}: {outliers} potential outliers")

# Do not automatically delete outliers.
# They may represent genuine fire observations.


# ==========================================
# 10. DATA VISUALIZATION
# ==========================================

# Original FRP distribution.
plt.figure(figsize=(8, 5))

sns.histplot(df["frp"], bins=50, kde=True)

plt.title("Original MODIS FRP Distribution")
plt.xlabel("FRP (MW)")
plt.ylabel("Frequency")

plt.show()


# Log-transformed FRP distribution.
# Used for visualization only.
plt.figure(figsize=(8, 5))

sns.histplot(
    np.log1p(df["frp"]),
    bins=50,
    kde=True
)

plt.title("Log-Transformed MODIS FRP Distribution")
plt.xlabel("log(1 + FRP)")
plt.ylabel("Frequency")

plt.show()


# Brightness vs FRP.
plt.figure(figsize=(8, 5))

sns.scatterplot(
    data=df,
    x="brightness",
    y="frp",
    alpha=0.5
)

plt.title("Brightness vs FRP")
plt.xlabel("Brightness (K)")
plt.ylabel("FRP (MW)")

plt.show()


# Brightness T31 vs FRP.
plt.figure(figsize=(8, 5))

sns.scatterplot(
    data=df,
    x="bright_t31",
    y="frp",
    alpha=0.5
)

plt.title("Bright_T31 vs FRP")
plt.xlabel("Bright_T31 (K)")
plt.ylabel("FRP (MW)")

plt.show()


# Original geographical distribution using FRP.
plt.figure(figsize=(10, 6))

plt.scatter(
    df["longitude"],
    df["latitude"],
    c=df["frp"],
    cmap="hot",
    alpha=0.6
)

plt.colorbar(label="FRP (MW)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")

plt.title(
    "MODIS Geographical Distribution of Fire Detections (Original FRP)"
)

plt.show()


# Log-transformed geographical distribution.
# Original FRP values remain unchanged.
plt.figure(figsize=(10, 6))

plt.scatter(
    df["longitude"],
    df["latitude"],
    c=np.log1p(df["frp"]),
    cmap="hot",
    alpha=0.6
)

plt.colorbar(label="log(1 + FRP)")
plt.xlabel("Longitude")
plt.ylabel("Latitude")

plt.title(
    "MODIS Geographical Distribution of Fire Detections (Log FRP)"
)

plt.show()


# Day vs Night detections.
plt.figure(figsize=(7, 5))

sns.countplot(
    data=df,
    x="daynight"
)

plt.title("MODIS Fire Detections: Day vs Night")
plt.xlabel("Day / Night")
plt.ylabel("Number of Detections")

plt.show()


# ==========================================
# 11. FINAL DATA INTEGRITY CHECKS
# ==========================================

print("\n========== FINAL DATA CHECKS ==========")

print("\nFinal Dataset Shape:", df.shape)

print("\nMissing Values:")
print(df.isnull().sum())

print("\nTotal Missing Values:", df.isnull().sum().sum())

print("\nDuplicate Rows:", df.duplicated().sum())

print(
    "\nInvalid Latitude:",
    ((df["latitude"] < -90) | (df["latitude"] > 90)).sum()
)

print(
    "\nInvalid Longitude:",
    ((df["longitude"] < -180) | (df["longitude"] > 180)).sum()
)

print("\nNegative FRP:", (df["frp"] < 0).sum())

print("\nZero FRP:", (df["frp"] == 0).sum())

print("\nUnique Acquisition Dates:")
print(df["acq_date"].dt.date.nunique())

print("\nUnique Spatial Grid Cells:")
print(df["spatial_grid_id"].nunique())

print("\nCoordinate Reference System:")
print(df["coordinate_reference_system"].unique())

print("\nUnique Countries:")
print(df["country_name"].nunique())

print("\nUnmatched Country Records:")

print(
    df[["country_name", "country_code", "continent"]]
    .isna()
    .any(axis=1)
    .sum()
)

print("\nFire Detections by Country (Top 20):")
print(df["country_name"].value_counts().head(20))

print("\nRemaining Fire Types:")
print(df["type"].value_counts(dropna=False))

print("\nRecords with Type = 2:")
print((df["type"] == 2).sum())

print("\nFinal Columns:")
print(df.columns.tolist())


# ==========================================
# 12. EXPORT CLEANED DATASET
# ==========================================

output_file = (
    PROJECT_FOLDER / "SA2018MODIS_Cleaned_Aligned.csv"
)

# Export original FRP values.
# Log transformation was only used for visualization.

df.to_csv(output_file, index=False)

print("\n==========================================")
print("MODIS DATA CLEANING COMPLETED SUCCESSFULLY!")
print("SPATIAL ALIGNMENT COMPLETED!")
print("TEMPORAL ALIGNMENT COMPLETED!")
print("COUNTRY ASSIGNMENT COMPLETED!")
print("UNMATCHED COUNTRY RECORDS REMOVED!")
print("TYPE 2 RECORDS REMOVED!")
print("==========================================")

print("\nCleaned Dataset Saved As:", output_file)

print("Final Number of Records:", len(df))
