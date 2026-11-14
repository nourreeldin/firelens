# FireLens Backend – Frontend Integration Summary

> This document is written for a **v0 / Next.js frontend agent** building a web UI on top of the FireLens read-only FastAPI backend. Everything a frontend needs to know about data shapes, filters, pagination, and error handling is captured here.

---

## 1. What FireLens Is

FireLens is a **read-only** REST API that exposes harmonised **MODIS** and **VIIRS** satellite active-fire detections sourced from NASA FIRMS. The underlying store is Supabase PostgreSQL + PostGIS. The API never creates or mutates data.

---

## 2. Base URL & OpenAPI

| Environment | Base URL |
|---|---|
| Local dev | `http://127.0.0.1:8000` |
| Versioned prefix | `http://127.0.0.1:8000/api/v1` |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |

> [!IMPORTANT]
> All meaningful frontend routes are under `/api/v1`. The unversioned `/health` and `/health/ready` paths exist only for container health probes.

---

## 3. CORS

The backend allows **`GET` and `OPTIONS`** from:

```
http://localhost:3000
http://127.0.0.1:3000
```

A Next.js dev server on port 3000 works out of the box. For production, the backend operator must add the deployed frontend origin to `CORS_ORIGINS`.

---

## 4. Authentication

No auth is required for most endpoints. The **single exception** is the CSV export:

- If the backend has `API_KEY` set, `GET /api/v1/exports/fires` requires the HTTP header `X-API-Key: <key>`.
- All other endpoints are open.

---

## 5. Shared Query Parameters (Filters)

The following filters apply to `/fires`, `/calendar`, all `/analytics/*` routes, and `/exports/fires`:

| Parameter | Type | Example | Notes |
|---|---|---|---|
| `start_date` | `YYYY-MM-DD` | `2025-07-01` | Inclusive acquisition date |
| `end_date` | `YYYY-MM-DD` | `2025-07-31` | Inclusive acquisition date |
| `region_id` | 3-letter ISO code | `EGY`, `USA`, `AUS` | Country code from `/regions`; validated server-side |
| `sensor` | string | `MODIS` or `VIIRS` | Case-insensitive |
| `min_latitude` | float | `25.0` | Bounding box – **all four required together** |
| `max_latitude` | float | `35.0` | Bounding box |
| `min_longitude` | float | `25.0` | Bounding box |
| `max_longitude` | float | `35.0` | Bounding box |

> [!WARNING]
> Supplying only **one** of `start_date`/`end_date` returns `422 Unprocessable Entity`. Always send both or neither.
> Similarly, all four bounding-box parameters must be provided together.

---

## 6. Endpoints Reference

### 6.1 `GET /api/v1/health`

Database-backed liveness check.

**Response `200`:**
```json
{ "status": "ok", "database": "connected" }
```

**Response `503`** when the database is unreachable.

---

### 6.2 `GET /api/v1/fires` — Paginated Fire Detections

**Extra parameters (fires only):**

| Parameter | Default | Range | Notes |
|---|---|---|---|
| `limit` | `100` | 1–1000 | Page size |
| `offset` | `0` | ≥ 0 | Pagination offset |

**Response `200` shape:**
```json
{
  "total": 352,
  "limit": 100,
  "offset": 0,
  "items": [
    {
      "id": "uuid-or-int",
      "latitude": 30.1234,
      "longitude": 31.5678,
      "geom": null,
      "acq_date": "2025-07-15",
      "acq_time": "1030",
      "acq_datetime_utc": "2025-07-15T10:30:00Z",
      "sensor": "VIIRS",
      "satellite": "NPP",
      "confidence": "high",
      "confidence_raw": "h",
      "country_code": "EGY",
      "country_name": "Egypt",
      "continent": "Africa",
      "spatial_grid_id": "some-grid"
    }
  ]
}
```

> [!NOTE]
> `confidence` is **normalised** to `"high"`, `"nominal"`, `"low"`, or `"unknown"`. `confidence_raw` is the original sensor value. See §10 for the full mapping.

**Error responses:** `404` if `region_id` not found, `422` on bad params, `503` on DB failure.

---

### 6.3 `GET /api/v1/fires/{id}` — Single Detection

Returns the same shape as one item in `items` above, or `404` if not found.

---

### 6.4 `GET /api/v1/regions` — Available Countries

Returns countries derived **at query time** from distinct `country_code` values in the hotspot table.

**Response `200` shape:**
```json
[
  {
    "id": "EGY",
    "name": "Egypt",
    "continent": "Africa",
    "hotspot_count": 12,
    "bbox": {
      "min_latitude": 22.0,
      "max_latitude": 31.7,
      "min_longitude": 24.7,
      "max_longitude": 36.9
    },
    "centroid": { "latitude": 26.8, "longitude": 30.8 },
    "hemisphere": "northern"
  }
]
```

> [!TIP]
> Use this endpoint to populate a **country selector / filter dropdown** in the UI. The `id` field is the value to send as `region_id` in other calls.

---

### 6.5 `GET /api/v1/calendar` — Zero-Filled Daily Counts

Returns one entry per calendar day in the range, including days with **zero** detections.

**Defaults:** If both dates are omitted → latest 30 days with data. Ranges capped at 366 days (`MAX_CALENDAR_DAYS`).

**Response `200` shape:**
```json
[
  { "date": "2025-07-01", "count": 0 },
  { "date": "2025-07-02", "count": 3 },
  ...
]
```

> [!TIP]
> Perfect for a **line/bar chart** of daily fire activity. Zero-filling is handled server-side, so no client-side gap-filling is needed.

---

### 6.6 `GET /api/v1/analytics/seasonal` — Seasonal Totals

Classifies each detection by its own latitude into northern/southern hemisphere, then into meteorological seasons (`DJF`, `MAM`, `JJA`, `SON`).

If dates are omitted → uses the latest year in the filtered dataset.

**Response `200` shape:**
```json
{
  "year": 2025,
  "data": [
    {
      "season_code": "JJA",
      "season_label": "Summer (JJA)",
      "hemisphere": "northern",
      "total": 148
    },
    {
      "season_code": "JJA",
      "season_label": "Winter (JJA)",
      "hemisphere": "southern",
      "total": 7
    }
  ]
}
```

> [!NOTE]
> Season labels are **hemisphere-aware**. Northern `JJA` → `Summer (JJA)`, Southern `JJA` → `Winter (JJA)`.

---

### 6.7 `GET /api/v1/analytics/comparison` — Historical Comparison

Compares selected period totals against prior-year baselines (mean & median).

**Extra parameter:**

| Parameter | Values | Default |
|---|---|---|
| `group_by` | `month` or `season` | `month` |

**Response when enough history (`status: "ok"`):**
```json
{
  "status": "ok",
  "baseline_years": 3,
  "data": [
    {
      "group": "2025-07",
      "observed": 48,
      "historical_mean": 32.3,
      "historical_median": 31.0,
      "difference_percent": 48.6
    }
  ]
}
```

**Response when insufficient history:**
```json
{
  "status": "insufficient_history",
  "baseline_years": 1,
  "data": [
    {
      "group": "2025-07",
      "observed": 48,
      "historical_mean": null,
      "historical_median": null,
      "difference_percent": null
    }
  ]
}
```

> [!IMPORTANT]
> **Currently always returns `insufficient_history`** because the dataset covers only 2025-06-20 → 2025-10-08 (one year). The frontend **must** handle this gracefully — show a banner or empty state rather than crashing.

---

### 6.8 `GET /api/v1/analytics/anomalies` — Monthly Anomaly Scores

Computes robust **modified Z-scores** (median + MAD) per calendar month vs prior years.

**Response shape (may also be `insufficient_history`):**
```json
{
  "status": "ok",
  "method": "modified_z_score",
  "formula": "0.6745 * (observed - median) / MAD",
  "thresholds": { "moderate": 2.5, "high": 3.5 },
  "baseline_years_available": 3,
  "data": [
    {
      "month": "2025-07",
      "observed": 48,
      "baseline_median": 31.0,
      "baseline_mad": 4.2,
      "score": 2.73,
      "severity": "moderate",
      "status": "ok",
      "baseline_years": 3
    }
  ]
}
```

**Row `status` values:**
| Value | Meaning |
|---|---|
| `ok` | Score computed normally |
| `insufficient_history` | Fewer than 3 prior years for this month |
| `insufficient_variance` | MAD = 0 and observation ≠ median |

**Severity values:** `null`, `"moderate"` (\|score\| ≥ 2.5), `"high"` (\|score\| ≥ 3.5).

---

### 6.9 `GET /api/v1/exports/fires` — Streamed CSV Download

Streams all matching detections as a CSV file using server-side cursor (no memory blow-up).

- **Content-Type:** `text/csv; charset=utf-8`
- **Filename:** `firelens_fires_<UTC-timestamp>.csv`
- **Auth:** Requires `X-API-Key` header if `API_KEY` is configured on the backend.
- Accepts all shared filters (no pagination params).

**Frontend usage:** Use `<a href="...">` download link or `fetch()` with `blob()` and `URL.createObjectURL`.

---

## 7. Error Handling Summary

| HTTP Status | Meaning | Frontend action |
|---|---|---|
| `200` | OK | Render data |
| `422` | Validation error (bad params, single date without partner, etc.) | Show inline error near filters |
| `404` | Region or detection not found | Show "not found" empty state |
| `503` | Database unavailable | Show full-page error banner |
| `500` | Unexpected server error | Show generic error message |

---

## 8. Data Coverage & Limitations

> [!CAUTION]
> The current dataset covers **2025-06-20 → 2025-10-08** only (35 rows). This affects the UI significantly:
> - `/analytics/comparison` and `/analytics/anomalies` will always return `insufficient_history`.
> - Date pickers should guide users to this window (or warn when outside it).
> - Any "trend over years" UI must degrade gracefully with a clear message.

---

## 9. Suggested UI Pages / Components

| Page / Component | Endpoints used |
|---|---|
| **Dashboard / Overview** | `/health`, `/regions`, `/calendar` |
| **Map View** | `/fires` (with bbox filters), `/regions` (for centroid markers) |
| **Country Filter Selector** | `/regions` |
| **Daily Activity Chart** (line/bar) | `/calendar` |
| **Seasonal Breakdown** (bar/pie) | `/analytics/seasonal` |
| **Historical Comparison** (bar with baseline) | `/analytics/comparison` |
| **Anomaly Heatmap / Table** | `/analytics/anomalies` |
| **Detection Detail Modal** | `/fires/{id}` |
| **CSV Export Button** | `/exports/fires` |

---

## 10. Confidence Normalization

| Sensor | Raw value | Normalized `confidence` |
|---|---|---|
| MODIS | ≥ 80 | `high` |
| MODIS | 40–79 | `nominal` |
| MODIS | < 40 | `low` |
| VIIRS | `h` | `high` |
| VIIRS | `n` | `nominal` |
| VIIRS | `l` | `low` |
| Any | missing/unrecognized | `unknown` |

---

## 11. Seasons Reference

| Code | Months | Northern label | Southern label |
|---|---|---|---|
| `DJF` | Dec–Feb | Winter (DJF) | Summer (DJF) |
| `MAM` | Mar–May | Spring (MAM) | Autumn (MAM) |
| `JJA` | Jun–Aug | Summer (JJA) | Winter (JJA) |
| `SON` | Sep–Nov | Autumn (SON) | Spring (SON) |

December is assigned to the DJF season ending in the **following year**.

---

## 12. Backend Tech Stack (for context)

| Component | Detail |
|---|---|
| Framework | FastAPI ≥ 0.115 |
| Async runtime | asyncpg (raw SQL, no ORM) |
| DB | PostgreSQL 15 + PostGIS via Supabase |
| Validation | Pydantic v2 |
| Server | Uvicorn |
| Python | 3.12+ |

---

## 13. Example Curl Calls (copy-paste for Postman/Insomnia)

```bash
# Health
curl "http://127.0.0.1:8000/api/v1/health"

# Paginated fires for Egypt, July 2025
curl "http://127.0.0.1:8000/api/v1/fires?start_date=2025-07-01&end_date=2025-07-31&region_id=EGY&limit=25"

# Bounding-box + sensor filter
curl "http://127.0.0.1:8000/api/v1/fires?min_latitude=25&max_latitude=35&min_longitude=25&max_longitude=35&sensor=viirs"

# Calendar (zero-filled daily counts)
curl "http://127.0.0.1:8000/api/v1/calendar?start_date=2025-10-01&end_date=2025-10-08&region_id=EGY"

# Seasonal analytics
curl "http://127.0.0.1:8000/api/v1/analytics/seasonal?start_date=2025-01-01&end_date=2025-12-31"

# Historical comparison (grouped by season)
curl "http://127.0.0.1:8000/api/v1/analytics/comparison?start_date=2025-01-01&end_date=2025-12-31&group_by=season"

# Anomaly scores
curl "http://127.0.0.1:8000/api/v1/analytics/anomalies?start_date=2025-01-01&end_date=2025-12-31"

# Download CSV for Egypt
curl -OJ "http://127.0.0.1:8000/api/v1/exports/fires?region_id=EGY"
```
