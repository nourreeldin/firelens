# FireLens API Reference

> **Version:** 1.0.0  
> **Base URL:** `http://127.0.0.1:8000`  
> **Versioned prefix:** `/api/v1`  
> **Interactive docs:** `/docs` (custom Swagger) · `/redoc`  
> **OpenAPI schema:** `/openapi.json`

All endpoints are **read-only** (`GET` / `OPTIONS`). There are no `POST`, `PUT`, `PATCH`, or `DELETE` operations.

---

## Table of Contents

1. [Global Conventions](#1-global-conventions)
2. [Shared Filters](#2-shared-filters)
3. [Error Responses](#3-error-responses)
4. [Root](#4-root-get-)
5. [Health](#5-health)
   - [GET /api/v1/health](#get-apiv1health)
   - [GET /health](#get-health-liveness-alias)
   - [GET /health/ready](#get-healthready-readiness-alias)
6. [Fires](#6-fires)
   - [GET /api/v1/fires](#get-apiv1fires)
   - [GET /api/v1/fires/{fire_id}](#get-apiv1firesfire_id)
7. [Regions](#7-regions)
   - [GET /api/v1/regions](#get-apiv1regions)
8. [Calendar](#8-calendar)
   - [GET /api/v1/calendar](#get-apiv1calendar)
9. [Analytics](#9-analytics)
   - [GET /api/v1/analytics/seasonal](#get-apiv1analyticsseasonal)
   - [GET /api/v1/analytics/comparison](#get-apiv1analyticscomparison)
   - [GET /api/v1/analytics/anomalies](#get-apiv1analyticsanomalies)
10. [Exports](#10-exports)
    - [GET /api/v1/exports/fires](#get-apiv1exportsfires)
11. [Schema Reference](#11-schema-reference)
12. [Confidence Normalization](#12-confidence-normalization)
13. [Season Classification](#13-season-classification)

---

## 1. Global Conventions

| Property | Value |
|---|---|
| Protocol | HTTP/1.1, HTTPS recommended in production |
| Allowed methods | `GET`, `OPTIONS` |
| Content-Type (responses) | `application/json` (CSV for export) |
| Date format | `YYYY-MM-DD` (ISO 8601) |
| Datetime format | ISO 8601 UTC, e.g. `2025-07-15T10:30:00Z` |
| Coordinate system | WGS 84 (EPSG 4326) |
| Pagination style | Offset (`limit` / `offset`) |
| Null handling | Optional fields are omitted or `null`; never fabricated |

### CORS

Allowed origins (default):

```
http://localhost:3000
http://127.0.0.1:3000
```

`Content-Disposition` is explicitly exposed so browsers can read the CSV filename.

### Authentication

The API is **open by default**. The only protected endpoint is `GET /api/v1/exports/fires`, and only when the `API_KEY` environment variable is set on the server.

| Endpoint | Auth required |
|---|---|
| All `/api/v1/*` except exports | None |
| `GET /api/v1/exports/fires` | `X-API-Key: <key>` header **if** `API_KEY` is configured |

When the key is required and missing or wrong, the server returns `401 Unauthorized`.

---

## 2. Shared Filters

The following query parameters are accepted by `/fires`, `/calendar`, all `/analytics/*` routes, and `/exports/fires`.

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `start_date` | `date` | `null` | `YYYY-MM-DD` | Inclusive acquisition-date lower bound |
| `end_date` | `date` | `null` | `YYYY-MM-DD` | Inclusive acquisition-date upper bound |
| `region_id` | `string` | `null` | Exactly 3 alpha characters, case-insensitive | Three-letter ISO country code (e.g. `EGY`, `USA`, `AUS`). Auto-uppercased. Must exist in the dataset or `404` is returned. |
| `sensor` | `string` | `null` | `MODIS` or `VIIRS` (case-insensitive) | Filter by satellite sensor |
| `min_latitude` | `float` | `null` | −90 ≤ value ≤ 90 | Bounding-box south edge |
| `max_latitude` | `float` | `null` | −90 ≤ value ≤ 90, > `min_latitude` | Bounding-box north edge |
| `min_longitude` | `float` | `null` | −180 ≤ value ≤ 180 | Bounding-box west edge |
| `max_longitude` | `float` | `null` | −180 ≤ value ≤ 180, > `min_longitude` | Bounding-box east edge |

> **Bounding-box rule:** All four bbox parameters must be supplied together. Providing only some returns `422`.  
> **Date rule:** Providing only one of `start_date` / `end_date` returns `422`. Always send both or neither.  
> **Date ordering rule:** `start_date` must be ≤ `end_date`, otherwise `422`.

Bounding-box queries use PostGIS `ST_Intersects(geom, ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326))`.

---

## 3. Error Responses

All error bodies follow the shape:

```json
{ "detail": "<human-readable message>" }
```

| Status | Trigger |
|---|---|
| `401 Unauthorized` | Missing or invalid `X-API-Key` on the export endpoint (when `API_KEY` is configured) |
| `404 Not Found` | `region_id` not in dataset, or `fire_id` does not exist |
| `422 Unprocessable Entity` | Invalid parameter values, bad date range, partial bbox |
| `500 Internal Server Error` | Unexpected query failure |
| `503 Service Unavailable` | Database connection lost or pool unavailable |

---

## 4. Root

### `GET /`

Returns a service info document. Not included in the OpenAPI schema.

**Response `200`:**
```json
{
  "name": "FireLens API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/api/v1/health",
  "api": "/api/v1"
}
```

---

## 5. Health

### `GET /api/v1/health`

**Tag:** `health`  
**Summary:** Service and database health  
**Auth:** None

Executes a lightweight read-only query (`SELECT 1`) against the database pool to confirm the connection is live.

**Response `200`:**
```json
{
  "status": "ok",
  "service": "FireLens API",
  "version": "1.0.0",
  "database": "connected"
}
```

| Field | Type | Description |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` on success |
| `service` | `string` | Application name from settings |
| `version` | `string` | Application version from settings |
| `database` | `"connected"` | Always `"connected"` on success |

**Response `503`:** Database is unavailable.

---

### `GET /health` _(liveness alias)_

Unversioned alias for container liveness probes. **Not in OpenAPI schema.**

**Response `200`:**
```json
{ "status": "ok" }
```

---

### `GET /health/ready` _(readiness alias)_

Unversioned alias for container readiness probes. Checks the database pool. **Not in OpenAPI schema.**

**Response `200`:**
```json
{ "status": "ready", "database": "connected" }
```

**Response `503`:** Database is unavailable.

---

## 6. Fires

### `GET /api/v1/fires`

**Tag:** `fires`  
**Summary:** List fire detections  
**Auth:** None

Returns paginated, filtered fire detections from `public.fire_hotspots`.

**Query Parameters:** All [shared filters](#2-shared-filters) plus:

| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `limit` | `integer` | `100` | 1–1000 | Page size |
| `offset` | `integer` | `0` | ≥ 0 | Number of records to skip |

**Response `200`:**
```json
{
  "data": [
    {
      "id": 1,
      "latitude": 30.1234,
      "longitude": 31.5678,
      "acq_date": "2025-07-15",
      "acq_time": 1030,
      "acq_datetime_utc": "2025-07-15T10:30:00Z",
      "sensor": "VIIRS",
      "confidence": "high",
      "confidence_raw": "h",
      "satellite": "NPP",
      "version": "2.0NRT",
      "daynight": "D",
      "brightness": 335.5,
      "brightness_thermal": 295.3,
      "scan": 0.39,
      "track": 0.36,
      "frp": 8.3,
      "country_code": "EGY",
      "country_name": "Egypt",
      "continent": "Africa",
      "spatial_grid_id": "grid-id-string"
    }
  ],
  "pagination": {
    "limit": 100,
    "offset": 0,
    "total": 352
  }
}
```

**`FireRecord` fields:**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | `integer` | No | Primary key |
| `latitude` | `float` | No | −90 to 90 |
| `longitude` | `float` | No | −180 to 180 |
| `acq_date` | `date` | No | Acquisition date |
| `acq_time` | `integer` | Yes | FIRMS acquisition time in `HHMM` format |
| `acq_datetime_utc` | `datetime` | Yes | Combined UTC acquisition datetime |
| `sensor` | `string` | Yes | `"MODIS"` or `"VIIRS"` |
| `confidence` | `string` | No | Normalized: `"high"`, `"nominal"`, `"low"`, `"unknown"` |
| `confidence_raw` | `string` | Yes | Original value from database before normalization |
| `satellite` | `string` | Yes | Satellite name (e.g. `"NPP"`, `"NOAA-20"`) |
| `version` | `string` | Yes | FIRMS collection version |
| `daynight` | `string` | Yes | `"D"` (day) or `"N"` (night) |
| `brightness` | `float` | Yes | Channel 21/22 brightness temperature (K), MODIS only |
| `brightness_thermal` | `float` | Yes | Channel 31 brightness temperature (K), MODIS only |
| `scan` | `float` | Yes | Along-scan pixel size (km) |
| `track` | `float` | Yes | Along-track pixel size (km) |
| `frp` | `float` | Yes | Fire Radiative Power (MW) |
| `country_code` | `string` | Yes | Three-letter ISO country code |
| `country_name` | `string` | Yes | Full country name |
| `continent` | `string` | Yes | Continent name |
| `spatial_grid_id` | `string` | Yes | Spatial grid cell identifier |

**`Pagination` fields:**

| Field | Type | Description |
|---|---|---|
| `limit` | `integer` | Page size used |
| `offset` | `integer` | Offset used |
| `total` | `integer` | Total matching records (before pagination) |

**Error responses:** `404` if `region_id` not found · `422` on invalid params · `503` on DB failure

---

### `GET /api/v1/fires/{fire_id}`

**Tag:** `fires`  
**Summary:** Get one fire detection  
**Auth:** None

**Path parameter:**

| Parameter | Type | Constraints | Description |
|---|---|---|---|
| `fire_id` | `integer` | ≥ 1 | Primary key of the detection record |

**Response `200`:** A single [`FireRecord`](#firelist-fields) object (same shape as one item in the `data` array above).

**Error responses:** `404` if the detection does not exist · `503` on DB failure

---

## 7. Regions

### `GET /api/v1/regions`

**Tag:** `regions`  
**Summary:** List countries represented in the dataset  
**Auth:** None

Regions are derived **at query time** from distinct `country_code` values in `public.fire_hotspots`. Counts, bounding boxes, and centroids are computed with PostGIS. This endpoint accepts **no query parameters**.

**Response `200`:**
```json
{
  "data": [
    {
      "id": "EGY",
      "country_code": "EGY",
      "name": "Egypt",
      "continent": "Africa",
      "hemisphere": "northern",
      "hotspot_count": 12,
      "bounding_box": {
        "min_latitude": 22.0,
        "min_longitude": 24.7,
        "max_latitude": 31.7,
        "max_longitude": 36.9
      },
      "centroid": {
        "latitude": 26.8,
        "longitude": 30.8
      }
    }
  ],
  "total": 15
}
```

**`RegionRecord` fields:**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `id` | `string` | No | Three-letter ISO country code (same as `country_code`). Use this as `region_id` in other calls. |
| `country_code` | `string` | No | Three-letter ISO country code |
| `name` | `string` | No | Full country name |
| `continent` | `string` | Yes | Continent name |
| `hemisphere` | `"northern" \| "southern"` | Yes | Based on the centroid latitude |
| `hotspot_count` | `integer` | No | Number of detections in the dataset |
| `bounding_box` | `BoundingBox` | Yes | PostGIS-computed geographic extent |
| `centroid` | `Centroid` | Yes | PostGIS-computed centroid of all hotspot geometries |

**`BoundingBox` fields:** `min_latitude`, `min_longitude`, `max_latitude`, `max_longitude` (all floats).  
**`Centroid` fields:** `latitude`, `longitude` (both floats).

**Response `200` envelope:**

| Field | Type | Description |
|---|---|---|
| `data` | `RegionRecord[]` | List of region records |
| `total` | `integer` | Count of records in `data` |

**Error responses:** `503` on DB failure

---

## 8. Calendar

### `GET /api/v1/calendar`

**Tag:** `calendar`  
**Summary:** Daily detection calendar  
**Auth:** None

Returns zero-filled daily fire counts. Days with no detections are included with `fire_count: 0`. Counts are generated in PostgreSQL using `generate_series` + `LEFT JOIN`.

**Query Parameters:** All [shared filters](#2-shared-filters). No extra parameters.

**Default date range:** When both `start_date` and `end_date` are omitted, the latest 30 days represented in the filtered dataset are used. The range is capped at `MAX_CALENDAR_DAYS` (default 366).

**Response `200`:**
```json
{
  "status": "ok",
  "data": [
    { "date": "2025-07-01", "fire_count": 0 },
    { "date": "2025-07-02", "fire_count": 3 },
    { "date": "2025-07-03", "fire_count": 1 }
  ],
  "meta": {
    "start_date": "2025-07-01",
    "end_date": "2025-07-31",
    "total_days": 31,
    "total_fires": 42,
    "region_id": "EGY",
    "sensor": null
  }
}
```

**`CalendarResponse` fields:**

| Field | Type | Description |
|---|---|---|
| `status` | `"ok" \| "no_data"` | `"no_data"` when no records match the filters |
| `data` | `CalendarDay[]` | Array of one entry per calendar day, ordered by date |
| `meta` | `CalendarMeta` | Filter echo and aggregate stats |

**`CalendarDay` fields:**

| Field | Type | Description |
|---|---|---|
| `date` | `date` | The calendar day (`YYYY-MM-DD`) |
| `fire_count` | `integer ≥ 0` | Number of detections (zero-filled) |

**`CalendarMeta` fields:**

| Field | Type | Description |
|---|---|---|
| `start_date` | `date \| null` | Actual start of the returned range |
| `end_date` | `date \| null` | Actual end of the returned range |
| `total_days` | `integer` | Number of calendar days in `data` |
| `total_fires` | `integer` | Sum of all `fire_count` values |
| `region_id` | `string \| null` | Applied region filter |
| `sensor` | `string \| null` | Applied sensor filter |

**Error responses:** `404` if `region_id` not found · `422` on invalid date range · `503` on DB failure

---

## 9. Analytics

All analytics routes share the same [shared filters](#2-shared-filters) and the same error responses (`404` region not found, `422` invalid range, `503` DB failure).

---

### `GET /api/v1/analytics/seasonal`

**Tag:** `analytics`  
**Summary:** Hemisphere-aware seasonal aggregates  
**Auth:** None

Returns monthly detection counts split by hemisphere, plus derived meteorological season aggregates. Each hotspot is classified by its own latitude:

- `latitude < 0` → `"southern"` hemisphere
- `latitude >= 0` → `"northern"` hemisphere (equator → northern)

Seasons: `DJF` (Dec–Feb), `MAM` (Mar–May), `JJA` (Jun–Aug), `SON` (Sep–Nov). December is assigned to the DJF season ending the **following year**.

**Query Parameters:** All [shared filters](#2-shared-filters). When dates are omitted, the latest year in the filtered dataset is used.

**Response `200`:**
```json
{
  "status": "ok",
  "data": [
    {
      "year": 2025,
      "month": 7,
      "month_name": "July",
      "hemisphere": "northern",
      "fire_count": 48
    }
  ],
  "seasonal": [
    {
      "season_year": 2025,
      "season": "JJA",
      "season_name": "Summer (JJA)",
      "hemisphere": "northern",
      "fire_count": 148
    },
    {
      "season_year": 2025,
      "season": "JJA",
      "season_name": "Winter (JJA)",
      "hemisphere": "southern",
      "fire_count": 7
    }
  ],
  "meta": {
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "total_fires": 352,
    "region_id": null,
    "sensor": null,
    "hemisphere_method": "latitude < 0 → southern, >= 0 → northern",
    "season_method": "meteorological DJF/MAM/JJA/SON"
  }
}
```

**`SeasonalResponse` fields:**

| Field | Type | Description |
|---|---|---|
| `status` | `"ok" \| "no_data"` | |
| `data` | `SeasonalMonthlyPoint[]` | Monthly counts per hemisphere |
| `seasonal` | `SeasonalPoint[]` | Season-level aggregates per hemisphere |
| `meta` | `SeasonalMeta` | Filter echo and methodology |

**`SeasonalMonthlyPoint` fields:**

| Field | Type | Description |
|---|---|---|
| `year` | `integer` | Calendar year |
| `month` | `integer` | 1–12 |
| `month_name` | `string` | e.g. `"July"` |
| `hemisphere` | `"northern" \| "southern"` | |
| `fire_count` | `integer ≥ 0` | |

**`SeasonalPoint` fields:**

| Field | Type | Description |
|---|---|---|
| `season_year` | `integer` | The year the season *ends* (DJF Dec is in the following year) |
| `season` | `string` | Code: `DJF`, `MAM`, `JJA`, or `SON` |
| `season_name` | `string` | Hemisphere-aware label (e.g. `"Summer (JJA)"`, `"Winter (JJA)"`) |
| `hemisphere` | `"northern" \| "southern"` | |
| `fire_count` | `integer ≥ 0` | |

**Season name reference:**

| Code | Northern | Southern |
|---|---|---|
| `DJF` | Winter (DJF) | Summer (DJF) |
| `MAM` | Spring (MAM) | Autumn (MAM) |
| `JJA` | Summer (JJA) | Winter (JJA) |
| `SON` | Autumn (SON) | Spring (SON) |

---

### `GET /api/v1/analytics/comparison`

**Tag:** `analytics`  
**Summary:** Compare activity with prior-year baselines  
**Auth:** None

Compares selected-period detections against historical totals from prior years. Requires at least **3 prior years** of data before statistics are computed. Periods must fall within a **single calendar year**.

**Query Parameters:** All [shared filters](#2-shared-filters) plus:

| Parameter | Type | Default | Values | Description |
|---|---|---|---|---|
| `group_by` | `string` | `"month"` | `"month"` or `"season"` | Historical grouping granularity |

When dates are omitted, the latest year in the filtered dataset is used.

**Response `200` (sufficient history):**
```json
{
  "status": "ok",
  "message": "Comparison computed successfully.",
  "meta": {
    "observed_start_date": "2025-01-01",
    "observed_end_date": "2025-12-31",
    "group_by": "month",
    "required_prior_years": 3,
    "available_prior_years": 4,
    "baseline_method": "mean and median across distinct prior years",
    "region_id": null,
    "sensor": null
  },
  "data": [
    {
      "period": "2025-07",
      "month": 7,
      "season": null,
      "season_name": null,
      "hemisphere": null,
      "observed_count": 48,
      "observed_years": 1,
      "historical_mean": 32.3,
      "historical_median": 31.0,
      "difference_percent": 48.6,
      "baseline_years": 4,
      "status": "ok"
    }
  ]
}
```

**Response `200` (insufficient history — currently always returned):**
```json
{
  "status": "insufficient_history",
  "message": "Insufficient prior-year data for statistical comparison.",
  "meta": { "...": "...", "available_prior_years": 1 },
  "data": [
    {
      "period": "2025-07",
      "observed_count": 48,
      "historical_mean": null,
      "historical_median": null,
      "difference_percent": null,
      "baseline_years": 1,
      "status": "insufficient_history"
    }
  ]
}
```

> **Current behavior:** Always returns `insufficient_history` because only one year of data exists (2025-06-20 → 2025-10-08).

**`ComparisonResponse` fields:**

| Field | Type | Description |
|---|---|---|
| `status` | `"ok" \| "insufficient_history" \| "no_data"` | Top-level status |
| `message` | `string` | Human-readable status explanation |
| `meta` | `ComparisonMeta` | Filter echo and baseline availability |
| `data` | `ComparisonRecord[]` | Per-group records |

**`ComparisonRecord` fields:**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `period` | `string` | No | Label, e.g. `"2025-07"` or `"2025-JJA-northern"` |
| `month` | `integer` | Yes | 1–12, when `group_by=month` |
| `season` | `string` | Yes | Season code, when `group_by=season` |
| `season_name` | `string` | Yes | Hemisphere-aware label, when `group_by=season` |
| `hemisphere` | `string` | Yes | `"northern"` or `"southern"`, when `group_by=season` |
| `observed_count` | `integer` | No | Detections in the selected period |
| `observed_years` | `integer` | No | Number of years in the observed window |
| `historical_mean` | `float` | Yes | Mean across prior years; `null` if insufficient history |
| `historical_median` | `float` | Yes | Median across prior years; `null` if insufficient history |
| `difference_percent` | `float` | Yes | `(observed − median) / median × 100`; `null` if insufficient history |
| `baseline_years` | `integer` | No | Number of prior years available for this group |
| `status` | `"ok" \| "insufficient_history"` | No | Per-row status |

---

### `GET /api/v1/analytics/anomalies`

**Tag:** `analytics`  
**Summary:** Robust monthly anomaly detection  
**Auth:** None

Computes a **modified Z-score** for each calendar month in the selected period by comparing the observed count to the same month in prior years.

**Formula:** `modified_z = 0.6745 × (observed − median) / MAD`

**Severity thresholds (configurable via env vars):**
- `|score| ≥ 2.5` → `"moderate"`
- `|score| ≥ 3.5` → `"high"`

Requires at least **3 prior years** per month. `MAD = 0` with `observed ≠ median` is reported as `insufficient_variance`. Periods must fall within a **single calendar year**.

**Query Parameters:** All [shared filters](#2-shared-filters). When dates are omitted, the latest year in the filtered dataset is used.

**Response `200`:**
```json
{
  "status": "ok",
  "message": "Anomaly detection computed successfully.",
  "meta": {
    "observed_start_date": "2025-01-01",
    "observed_end_date": "2025-12-31",
    "required_prior_years": 3,
    "available_prior_years": 4,
    "method": "modified_z_score",
    "score_formula": "0.6745 * (observed - median) / MAD",
    "moderate_threshold": 2.5,
    "high_threshold": 3.5,
    "region_id": null,
    "sensor": null
  },
  "data": [
    {
      "date": "2025-07-01",
      "period": "2025-07",
      "month": 7,
      "observed_count": 48,
      "historical_mean": 32.3,
      "historical_median": 31.0,
      "mad": 4.2,
      "anomaly_score": 2.73,
      "severity": "moderate",
      "direction": "above",
      "is_anomaly": true,
      "baseline_years": 4,
      "status": "ok"
    }
  ]
}
```

**`AnomalyResponse` fields:**

| Field | Type | Description |
|---|---|---|
| `status` | `"ok" \| "insufficient_history" \| "no_data"` | Top-level status |
| `message` | `string` | Human-readable explanation |
| `meta` | `AnomalyMeta` | Methodology and threshold values |
| `data` | `AnomalyRecord[]` | Per-month anomaly records |

**`AnomalyRecord` fields:**

| Field | Type | Nullable | Description |
|---|---|---|---|
| `date` | `date` | No | First day of the month |
| `period` | `string` | No | `"YYYY-MM"` label |
| `month` | `integer` | No | 1–12 |
| `observed_count` | `integer` | No | Detections in this month |
| `historical_mean` | `float` | Yes | Mean of same month across prior years |
| `historical_median` | `float` | Yes | Median of same month across prior years |
| `mad` | `float` | Yes | Median Absolute Deviation |
| `anomaly_score` | `float` | Yes | Modified Z-score; `null` if not computable |
| `severity` | `"normal" \| "moderate" \| "high"` | Yes | `null` if not computable |
| `direction` | `"above" \| "below" \| "normal"` | Yes | `null` if not computable |
| `is_anomaly` | `boolean` | No | `true` if severity is `moderate` or `high` |
| `baseline_years` | `integer` | No | Prior years available for this month |
| `status` | `"ok" \| "insufficient_history" \| "insufficient_variance"` | No | Per-row computation status |

**Row status values:**

| Value | Meaning |
|---|---|
| `ok` | Score computed normally |
| `insufficient_history` | Fewer than 3 prior years available for this month |
| `insufficient_variance` | MAD = 0 and observed ≠ median (division by zero avoided) |

> **Current behavior:** Always returns `insufficient_history` at the top level because only one year of data exists.

---

## 10. Exports

### `GET /api/v1/exports/fires`

**Tag:** `exports`  
**Summary:** Export fire detections as CSV  
**Auth:** `X-API-Key` header required **only if** `API_KEY` is configured server-side

Streams all matching detections as a downloadable CSV attachment. Uses an asyncpg server-side cursor with configurable batch size (`EXPORT_BATCH_SIZE`, default 500), so the full result set is never loaded into memory.

**Query Parameters:** All [shared filters](#2-shared-filters). No pagination parameters (`limit` / `offset` are ignored — all matching rows are exported).

**Request headers (conditional):**

| Header | Required when | Description |
|---|---|---|
| `X-API-Key` | `API_KEY` env var is set | Shared secret for export access |

**Response `200`:**

| Property | Value |
|---|---|
| `Content-Type` | `text/csv; charset=utf-8` |
| `Content-Disposition` | `attachment; filename="firelens_fires_<UTC-timestamp>.csv"` |
| `Cache-Control` | `no-store` |
| `X-Content-Type-Options` | `nosniff` |

The CSV includes a header row followed by one row per detection. Text cells starting with `=`, `+`, `-`, `@`, tab (`\t`), or carriage return (`\r`) (after leading whitespace) are prefixed with `'` to prevent spreadsheet formula injection.

**Example filename:** `firelens_fires_20251015_143022.csv`

**Client-side download (fetch):**
```js
const response = await fetch('/api/v1/exports/fires?region_id=EGY', {
  headers: { 'X-API-Key': 'your-key' } // omit if no key configured
});
const blob = await response.blob();
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = response.headers.get('Content-Disposition')
  .match(/filename="(.+)"/)[1];
a.click();
```

**Error responses:** `401` if key required and missing/wrong · `404` if `region_id` not found · `422` on invalid params · `503` on DB failure

---

## 11. Schema Reference

### `FireFilters` (shared query model)

```
start_date?    date              Inclusive lower bound
end_date?      date              Inclusive upper bound
region_id?     string[3 alpha]   Three-letter country code, auto-uppercased
sensor?        "MODIS"|"VIIRS"   Case-insensitive
min_latitude?  float[-90..90]    Bbox south edge  ─┐
max_latitude?  float[-90..90]    Bbox north edge   │ All four required together
min_longitude? float[-180..180]  Bbox west edge    │ min < max enforced
max_longitude? float[-180..180]  Bbox east edge   ─┘
```

### `FireRecord`

```
id                  integer         Primary key
latitude            float           WGS84 latitude
longitude           float           WGS84 longitude
acq_date            date            Acquisition date
acq_time?           integer|null    HHMM format
acq_datetime_utc?   datetime|null   UTC acquisition datetime
sensor?             string|null
confidence          ConfidenceLevel Normalized: high|nominal|low|unknown
confidence_raw?     string|null     Pre-normalization value
satellite?          string|null
version?            string|null     FIRMS collection version
daynight?           string|null     "D" or "N"
brightness?         float|null      Channel 21/22 temp (K), MODIS
brightness_thermal? float|null      Channel 31 temp (K), MODIS
scan?               float|null      Along-scan pixel size (km)
track?              float|null      Along-track pixel size (km)
frp?                float|null      Fire Radiative Power (MW)
country_code?       string|null
country_name?       string|null
continent?          string|null
spatial_grid_id?    string|null
```

### `ConfidenceLevel` (enum)

| Value | Description |
|---|---|
| `"high"` | MODIS ≥ 80 or VIIRS `"h"` |
| `"nominal"` | MODIS 40–79 or VIIRS `"n"` |
| `"low"` | MODIS < 40 or VIIRS `"l"` |
| `"unknown"` | Missing, null, or unrecognized value |

---

## 12. Confidence Normalization

| Sensor | Raw value | Normalized |
|---|---|---|
| MODIS | ≥ 80 | `high` |
| MODIS | 40–79 | `nominal` |
| MODIS | < 40 | `low` |
| VIIRS | `"h"` | `high` |
| VIIRS | `"n"` | `nominal` |
| VIIRS | `"l"` | `low` |
| Any | missing / unrecognized | `unknown` |

Unknown values are **preserved**, never guessed or fabricated.

---

## 13. Season Classification

Each detection is assigned a hemisphere from its own latitude, then a season from its acquisition month.

| Code | Months | Northern name | Southern name |
|---|---|---|---|
| `DJF` | Dec, Jan, Feb | Winter (DJF) | Summer (DJF) |
| `MAM` | Mar, Apr, May | Spring (MAM) | Autumn (MAM) |
| `JJA` | Jun, Jul, Aug | Summer (JJA) | Winter (JJA) |
| `SON` | Sep, Oct, Nov | Autumn (SON) | Spring (SON) |

> **December rule:** December is assigned to the DJF season that ends in the **following year**, so a detection on 2025-12-15 belongs to `season_year=2026, season=DJF`.

---

## Quick Reference

```bash
# Health
curl http://127.0.0.1:8000/api/v1/health

# Fires — paginated, filtered
curl "http://127.0.0.1:8000/api/v1/fires?start_date=2025-07-01&end_date=2025-07-31&region_id=EGY&limit=25"

# Fires — bounding box
curl "http://127.0.0.1:8000/api/v1/fires?min_latitude=25&max_latitude=35&min_longitude=25&max_longitude=35&sensor=VIIRS"

# Single detection
curl http://127.0.0.1:8000/api/v1/fires/1

# Regions
curl http://127.0.0.1:8000/api/v1/regions

# Calendar (zero-filled daily counts)
curl "http://127.0.0.1:8000/api/v1/calendar?start_date=2025-10-01&end_date=2025-10-08&region_id=EGY"

# Seasonal analytics
curl "http://127.0.0.1:8000/api/v1/analytics/seasonal?start_date=2025-01-01&end_date=2025-12-31"

# Historical comparison (by season)
curl "http://127.0.0.1:8000/api/v1/analytics/comparison?start_date=2025-01-01&end_date=2025-12-31&group_by=season"

# Anomaly detection
curl "http://127.0.0.1:8000/api/v1/analytics/anomalies?start_date=2025-01-01&end_date=2025-12-31"

# CSV export
curl -OJ "http://127.0.0.1:8000/api/v1/exports/fires?region_id=EGY"

# CSV export with API key
curl -OJ -H "X-API-Key: your-key" "http://127.0.0.1:8000/api/v1/exports/fires"
```

