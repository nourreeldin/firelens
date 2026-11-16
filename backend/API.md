<p><img src="app/static/firelens-wordmark.svg" alt="FireLens - Earth observation" width="253" height="64" /></p>

# FireLens API Reference

Base URL: `http://127.0.0.1:8000/api/v1`

Swagger/OpenAPI is served at `/docs`; ReDoc is served at `/redoc`. All routes
are read-only `GET` endpoints. CSV exports require `X-API-Key` only when
`API_KEY` is configured.

## Data products

| Table | Product | Routes |
| --- | --- | --- |
| `public.fire_hotspots` | Standardized raw satellite observations | `/fires`, `/calendar`, top-level `/analytics/*`, `/exports/fires` |
| `public.harmonized_activity` | Corrected activity by region/grid/day/method | `/harmonization*`, `/exports/harmonization` |
| `public.validation_reports` | Candidate-pair QA reports | `/validation`, `/exports/validation` |
| `public.regions` | Persisted integer-ID regions | `/regions/catalog` |

The existing `/regions` route still derives country filters from `fire_hotspots`
and returns three-letter country codes. Raw-fire `region_id=EGY` remains a string
country-code filter. Harmonized and validation routes use `region_pk=1` for the
integer `public.regions.id`; the two identifiers are intentionally separate.

## Route index

| Method | Path | Product |
| --- | --- | --- |
| GET | `/health` | Database health |
| GET | `/fires` | Paginated raw detections |
| GET | `/fires/{id}` | One raw detection |
| GET | `/regions` | Countries represented in hotspot data |
| GET | `/regions/catalog` | Persisted integer-ID regions |
| GET | `/calendar` | Raw detection calendar |
| GET | `/analytics/seasonal` | Raw detection seasonality |
| GET | `/analytics/comparison` | Raw detection historical comparison |
| GET | `/analytics/anomalies` | Raw detection anomaly scores |
| GET | `/exports/fires` | Raw detection CSV |
| GET | `/harmonization` | Corrected activity records |
| GET | `/harmonization/calendar` | Corrected daily activity |
| GET | `/harmonization/analytics/seasonal` | Corrected monthly and seasonal activity |
| GET | `/harmonization/analytics/comparison` | Corrected activity vs prior years |
| GET | `/harmonization/analytics/anomalies` | Corrected activity anomalies |
| GET | `/validation` | Validation reports |
| GET | `/exports/harmonization` | Corrected activity CSV |
| GET | `/exports/validation` | Validation CSV |

## Raw detections

`GET /fires` accepts inclusive `start_date` and `end_date`, country-code
`region_id`, `sensor`, a complete four-coordinate bounding box, `limit` (1–1000,
default 100), and `offset` (default 0). Its response is:

```json
{
  "data": [
    {
      "id": 1,
      "source_detection_id": "example-viirs-001",
      "latitude": 30.04,
      "longitude": 31.23,
      "acq_date": "2020-07-15",
      "sensor": "VIIRS",
      "confidence": "high",
      "confidence_raw": "h",
      "country_code": "EGY"
    }
  ],
  "pagination": {"limit": 100, "offset": 0, "total": 1}
}
```

Optional fire fields are omitted from this example. `confidence` is normalized
to `high`, `nominal`, `low`, or `unknown`; `confidence_raw` preserves the stored
value. `GET /fires/{id}` returns one `FireRecord` directly or 404.

`id` is the numeric database identity used by `/fires/{id}`.
`source_detection_id` is a separate nullable **string**. Event membership joins
use `fire_event_members.detection_id = fire_hotspots.source_detection_id`;
overlap joins use `fire_overlap_pairs.detection_id_a` and `detection_id_b`
against that same text column on each side. Never convert these identifiers
to numbers or join them to `fire_hotspots.id`. Event and overlap routes are
not currently exposed by this API.

The response also includes nullable `bright_t31` (MODIS), `bright_ti4` and
`bright_ti5` (VIIRS), `instrument`, `source_file`, `fire_type`,
`coordinate_reference_system`, `hour`, `minute`, `year`, `month`, `day`,
`day_of_year`, `grid_lat`, `grid_lon`, and `created_at`. Missing values remain
JSON `null`; `confidence_raw` and `version` retain their stored strings.
Normalized `confidence` remains `unknown` when the raw value is missing or
unrecognized. FRP is in MW. `acq_time` is integer HHMM (`32` means 00:32 UTC);
prefer the timezone-bearing `acq_datetime_utc` for timelines. Use
`[longitude, latitude]` for GeoJSON points. Bounding-box filters use these
coordinates when the nullable PostGIS `geom` is missing.

`GET /regions` returns `{ "data": RegionRecord[], "total": number }`. Its IDs
are three-letter country codes. `GET /regions/catalog` returns persisted region
rows with integer `id`, `name`, `slug`, optional `country_code`, description,
and optional geographic bounds and `created_at`. Obtain integer IDs from this
catalog instead of assuming a particular country has ID 1.

`GET /calendar` returns the unchanged raw-detection contract:

```json
{
  "status": "ok",
  "data": [{"date": "2020-07-02", "fire_count": 3}],
  "meta": {
    "start_date": "2020-07-01",
    "end_date": "2020-07-31",
    "total_days": 31,
    "total_fires": 3,
    "region_id": "EGY",
    "sensor": null
  }
}
```

The top-level seasonal, comparison, and anomaly endpoints also remain based on
raw `fire_hotspots` records. Their response models are `SeasonalResponse`,
`ComparisonResponse`, and `AnomalyResponse` in the generated OpenAPI schema.

## Harmonized activity

### `GET /harmonization`

Filters: `start_date`, `end_date`, `region_pk`, `spatial_grid_id`, and
`method_version`. Pagination: `limit` (1–1000, default 100) and `offset`
(default 0).

The imported 2018–2020 dataset uses **`daily-grid-modis-equivalent-v1`**.
Use that value for the corrected frontend views. The old
`daily-grid-raw-counts-v1` filter returns no imported activity rows. Omitting
`method_version` includes all methods; the API does not silently substitute a
method for an explicitly supplied filter. Response envelope:

```json
{
  "status": "ok",
  "data": [
    {
      "id": 1,
      "region_id": 1,
      "country_code": "EGY",
      "activity_date": "2020-07-15",
      "spatial_grid_id": "grid-001",
      "modis_count": 10,
      "viirs_count": 18,
      "harmonized_count": 5.819,
      "correction_factor": 0.091,
      "uncertainty": 0.027,
      "method_version": "daily-grid-modis-equivalent-v1",
      "created_at": "2020-07-16T12:00:00Z"
    }
  ],
  "pagination": {"limit": 100, "offset": 0, "total": 1}
}
```

Values are illustrative, not a fitted-metrics report.
`harmonized_count = (modis_count + correction_factor * viirs_count) / 2`
is a fractional hotspot detection index. Preserve its decimals in frontend
state, calculations, and chart data. `modis_count` and `viirs_count` are raw
integer counts. Region assignment, country code, grid ID, corrected count,
factor, and uncertainty may be `null`.

`uncertainty = viirs_count * SE(correction_factor) / 2` covers variation in
the country factor estimated with month blocks. It excludes coverage, clouds,
missed detections, and grid-level predictive error. Rows sharing a country
factor share uncertainty; do not combine their errors as independent values.

### `GET /harmonization/calendar`

Accepts the same date and activity filters. With no dates, returns the latest
30 days in the filtered dataset. Date ranges are capped by
`MAX_CALENDAR_DAYS` (default 366). Rows are separate by date and
`method_version`:

```json
{
  "status": "ok",
  "data": [
    {
      "date": "2020-07-02",
      "method_version": "daily-grid-modis-equivalent-v1",
      "harmonized_activity": 1.1365,
      "modis_count": 2,
      "viirs_count": 3,
      "grid_records": 1,
      "uncertainty": 0.0045
    }
  ],
  "meta": {
    "start_date": "2020-07-01",
    "end_date": "2020-07-30",
    "total_days": 30,
    "total_harmonized_activity": 1.1365,
    "total_modis_count": 2,
    "total_viirs_count": 3,
    "region_pk": 1,
    "spatial_grid_id": null,
    "method_versions": ["daily-grid-modis-equivalent-v1"],
    "aggregation_method": "..."
  }
}
```

Daily activity and raw source counts are summed across matching grid rows within
each method version. Dates without grid records have `grid_records: 0`, zero raw
counts, and `harmonized_activity: null`. If any matching grid row has a null
corrected count, that day's corrected total and the calendar's overall
corrected total remain null. A stored numeric zero remains zero.
When one day/version includes multiple grid rows,
`uncertainty` is `null`; the API does not invent an uncertainty aggregation
rule. Totals across multiple method versions are also `null` to avoid combining
different corrections.

### Harmonized analytics

The harmonized endpoints live under `/harmonization/analytics/` so the existing
raw analytics keep their response and meaning:

- `/seasonal` returns monthly totals and DJF/MAM/JJA/SON codes, separated by
  method version. December belongs to the season ending in the next year.
- `/comparison` compares monthly observed totals with full-month totals from
  prior years of the same method version. Its observation period must fit in
  one calendar year.
- `/anomalies` compares monthly totals with the same calendar month in prior
  years, using the median, MAD, and the modified Z-score.

Dates default to the latest represented year for seasonal and historical
analytics. Comparison and anomalies require one calendar year. The minimum
history defaults to three years; insufficient statistics remain `null` and are
marked `insufficient_history`. Each endpoint accepts the harmonized filters
above. If `method_version` is omitted, output rows remain separate by version.

The harmonized table does not contain grid latitude. Its seasonal endpoint
therefore returns season codes without the hemisphere-specific names used by
raw-fire analytics.

## Validation

### `GET /validation`

Accepts `region_pk`, `method_version`, `start_date`, `end_date`, `limit`, and
`offset`. Date filters return reports whose validation period overlaps the
requested interval. Fields include `validation_period_start`,
`validation_period_end`, `mae`, `rmse`, `bias`, `sample_size`, and `notes`.
The imported reports use **`pair-integrity-1km-30min-v1`**. They summarize
candidate-pair QA; `sample_size` counts validated overlap pairs. Their nullable
`mae`, `rmse`, and `bias` are not the held-out 2020 calibration metrics.
Request validation separately with its own method version; joining reports
to activity by equal `method_version` produces no match in this dataset.
Region, country code, validation dates, metrics, sample size, and notes can be
null and must remain null in the frontend.

The envelope is `{ "status": "ok", "data": ValidationRecord[], "pagination":
{ "limit": number, "offset": number, "total": number } }`.

## CSV exports

- `/exports/fires` exports raw detections, including the appended source text
  identifier, native sensor bands, source metadata, date/grid parts, and created
  timestamp. Read CSV columns by header name; nulls are empty cells.
- `/exports/harmonization` exports the filtered corrected activity rows.
- `/exports/validation` exports the filtered validation reports.

All exports stream from server-side cursors, set an attachment filename, and
sanitize text cells that could be interpreted as spreadsheet formulas. Include
`X-API-Key` when `API_KEY` is configured.

## Frontend integration

Generate full TypeScript types from `/openapi.json`. JSON dates are `YYYY-MM-DD`
strings; timestamps include a timezone. Represent nullable numbers as
`number | null`, and display null as unavailable instead of converting it to
zero. Distinguish an empty result (`data: []`) from a network error and from
`insufficient_history` or `insufficient_variance` analytics results. The
2018–2020 dataset has at most two prior years for 2020, fewer than the default
three-year history requirement.

Fetch the catalog, resolve the selected country to its integer ID, and request
activity and QA independently. This example uses the latest represented dates
instead of the current date, which is outside the imported study period:

```ts
const API_BASE = "http://127.0.0.1:8000/api/v1";
const ACTIVITY_METHOD = "daily-grid-modis-equivalent-v1";
const QA_METHOD = "pair-integrity-1km-30min-v1";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`FireLens request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

type CatalogRegion = { id: number; country_code: string | null };
const catalog = await getJson<{ data: CatalogRegion[]; total: number }>(
  "/regions/catalog"
);
const egypt = catalog.data.find(region => region.country_code === "EGY");
if (!egypt) throw new Error("Egypt is unavailable in the region catalog");

const activityQuery = new URLSearchParams({
  region_pk: String(egypt.id), method_version: ACTIVITY_METHOD
});
const qaQuery = new URLSearchParams({
  region_pk: String(egypt.id), method_version: QA_METHOD
});
// ActivityCalendarResponse / ValidationListResponse are generated OpenAPI types.
const [calendar, validation] = await Promise.all([
  getJson<ActivityCalendarResponse>(`/harmonization/calendar?${activityQuery}`),
  getJson<ValidationListResponse>(`/validation?${qaQuery}`)
]);
const chartPoints = calendar.data.map(row => ({
  date: row.date,
  value: row.harmonized_activity // Preserve fractional values and null gaps.
}));
```

For explicit study ranges, add both `start_date=2020-01-01` and
`end_date=2020-12-31` to calendar or analytics requests. On `/fires`, use
`region_id=EGY` instead of `region_pk`. Paginated list routes return
`pagination.total`; advance `offset` by the returned `pagination.limit` until
the full result is loaded. Configure the backend's `CORS_ORIGINS` with the
frontend's origin when running on a different port.

## Error responses

Validation errors use HTTP 422. Unknown fire IDs or region identifiers use
404. Database connection failures use 503; query failures use a generic 500.
Date ranges for comparison/anomaly analytics must stay within one calendar
year.
