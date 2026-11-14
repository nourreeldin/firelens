# FireLens Backend

Read-only FastAPI service for exploring harmonized **MODIS** and **VIIRS**
active-fire detections from NASA FIRMS. The API uses **parameterized raw SQL**
through an asyncpg connection pool against Supabase PostgreSQL + PostGIS. There
is no ORM and the API never creates or alters database objects.

> Satellite detections are observations, not confirmed fire boundaries. Sensor
> differences, overpass timing, clouds, and detection limits matter.

## Requirements

- Python 3.12+
- PostgreSQL 15+ with PostGIS
- An existing `DATABASE_URL` (the Supabase Session Pooler URL is supported)
- A NASA FIRMS map key only for ingestion jobs, not for serving this API

## Quick start

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set DATABASE_URL in .env to the existing Supabase connection string.

uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`, with OpenAPI/Swagger at
`http://127.0.0.1:8000/docs` and ReDoc at `http://127.0.0.1:8000/redoc`.

Both `postgresql://` and `postgresql+asyncpg://` URL schemes are accepted. The
latter is normalized internally, so the existing Supabase `DATABASE_URL` can be
reused without editing `.env`.

On startup the application opens an asyncpg pool and runs `SELECT 1`. On
shutdown it closes the pool. `AUTO_CREATE_TABLES` no longer exists: schema
management is external to the API.

## Tests

Tests use mocked repositories/services and never connect to the production
database:

```bash
cd backend
pytest -q
```

The suite covers endpoint validation, pagination, region validation, zero-filled
calendar aggregation, seasonal grouping, insufficient-history responses,
median/MAD scoring, CSV streaming, formula sanitization, and SQL parameter
construction.

## Supabase and data

The canonical harmonized dataset is `public.fire_hotspots`. Important fields
include `latitude`, `longitude`, `geom`, `acq_date`, `acq_time`,
`acq_datetime_utc`, `sensor`, `confidence`, `satellite`, `country_code`,
`country_name`, `continent`, and `spatial_grid_id`.

- Geometry is `geometry(Point, 4326)` with a GiST index.
- Bounding-box queries use `ST_Intersects(geom, ST_MakeEnvelope(..., 4326))`.
- No production tables or indexes were modified by this API.
- The API role in the current environment bypasses RLS; production deployments
  should use an explicit least-privilege role and policies.
- The current dataset covers **2025-06-20 through 2025-10-08** only. Historical
  comparison and anomaly endpoints therefore return `insufficient_history`
  until at least three prior years are loaded.
- `public.fire_daily_counts` is not used by the API because it lacks the
  geographic dimensions required for these filters.

## API

All required feature routes are under `/api/v1`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Database-backed health check |
| `GET` | `/api/v1/fires` | Paginated, filtered detections |
| `GET` | `/api/v1/fires/{id}` | One detection |
| `GET` | `/api/v1/regions` | Countries derived from hotspot data |
| `GET` | `/api/v1/calendar` | Zero-filled daily counts |
| `GET` | `/api/v1/analytics/seasonal` | Monthly and hemisphere-aware seasonal totals |
| `GET` | `/api/v1/analytics/comparison` | Selected period vs prior-year baselines |
| `GET` | `/api/v1/analytics/anomalies` | Robust median/MAD monthly anomalies |
| `GET` | `/api/v1/exports/fires` | Streamed CSV export |

Unversioned `/health` and `/health/ready` aliases remain available for container
platforms and are excluded from the OpenAPI schema. There are no POST, PUT,
PATCH, or DELETE endpoints.

### Shared filters

`/api/v1/fires`, `/calendar`, all analytics routes, and `/exports/fires` accept:

| Parameter | Notes |
| --- | --- |
| `start_date` | Inclusive acquisition date (`YYYY-MM-DD`) |
| `end_date` | Inclusive acquisition date (`YYYY-MM-DD`) |
| `region_id` | Three-letter country code such as `EGY`, `USA`, or `AUS`; validated against available records |
| `sensor` | `MODIS` or `VIIRS` (case-insensitive) |
| `min_latitude`, `max_latitude`, `min_longitude`, `max_longitude` | Bounding box; all four required together |

`/api/v1/fires` also accepts `limit` (1–1000, default 100) and `offset`
(default 0). `region_id` is intentionally retained for API consistency but is a
country code, not an integer region ID.

### Regions

Regions are derived at query time from distinct `country_code` values. Each
record includes the country name, continent, hotspot count, PostGIS bounding
box, centroid, and centroid-based hemisphere. `id` is the three-letter country
code.

### Calendar

Daily counts are generated in PostgreSQL with `generate_series` and
`LEFT JOIN`, so days without detections are returned with zero. If both dates
are omitted, the latest 30 days represented by the filtered dataset are used.
Supplying only one date returns a 422 response. Ranges are capped by
`MAX_CALENDAR_DAYS` (default 366).

### Seasons

Each hotspot is classified by its own latitude:

- `latitude < 0` → southern hemisphere
- `latitude >= 0` → northern hemisphere (the equator is grouped with northern)

Meteorological seasons are `DJF` (Dec–Feb), `MAM` (Mar–May), `JJA` (Jun–Aug),
and `SON` (Sep–Nov). December is assigned to the DJF season ending in the
following year. Season labels are hemisphere-aware, for example:

- Northern `JJA` → `Summer (JJA)`
- Southern `JJA` → `Winter (JJA)`
- Southern `DJF` → `Summer (DJF)`

If dates are omitted, seasonal analytics use the latest year in the filtered
dataset.

### Historical comparison

`/api/v1/analytics/comparison` accepts `group_by=month` (default) or
`group_by=season`. It compares the selected period with totals from prior years
ending before the observed start year. Mean and median are computed across
distinct prior years.

At least **three prior years** are required before statistics are returned.
Otherwise the response has `status: "insufficient_history"`, per-group
`historical_mean`, `historical_median`, and `difference_percent` are `null`, and
`baseline_years` reports the actual available count. No historical values are
fabricated.

Comparison periods must fall within a single calendar year. If dates are
omitted, the latest year in the filtered dataset is used.

### Anomaly detection

`/api/v1/analytics/anomalies` computes monthly totals and compares each month
with the distribution of the same calendar month in prior years.

- Baseline center: median
- Robust scale: median absolute deviation (MAD)
- Score: `modified_z = 0.6745 * (observed - median) / MAD`
- Minimum history: three prior years
- Severity: `|score| >= 2.5` moderate, `|score| >= 3.5` high
- `MAD = 0`: if the observation equals the median, the score is `0`; otherwise
  the row is reported as `insufficient_variance` rather than dividing by zero.

The response includes the method, formula, thresholds, available prior years,
per-row baseline years, and explicit status fields. Anomaly periods must fall
within a single calendar year.

### Confidence normalization

Every detection returns both normalized `confidence` and original
`confidence_raw`.

| Sensor | Raw value | Normalized |
| --- | --- | --- |
| MODIS | `>= 80` | `high` |
| MODIS | `40–79` | `nominal` |
| MODIS | `< 40` | `low` |
| VIIRS | `h` | `high` |
| VIIRS | `n` | `nominal` |
| VIIRS | `l` | `low` |
| Any | missing or unrecognized | `unknown` |

Unknown values are preserved rather than guessed.

### CSV export

`GET /api/v1/exports/fires` streams matching rows with an asyncpg server-side
cursor and batch size `EXPORT_BATCH_SIZE`. It does not build the full result set
in memory.

- Media type: `text/csv; charset=utf-8`
- Attachment filename: `firelens_fires_<UTC timestamp>.csv`
- Text cells beginning with `=`, `+`, `-`, `@`, tab, or carriage return after
  leading whitespace are prefixed with `'` to mitigate spreadsheet formula
  injection.
- If `API_KEY` is configured, requests must include `X-API-Key`.

### Examples

```bash
curl "http://127.0.0.1:8000/api/v1/health"

curl "http://127.0.0.1:8000/api/v1/fires?start_date=2025-07-01&end_date=2025-07-31&region_id=EGY&limit=25"

curl "http://127.0.0.1:8000/api/v1/fires?min_latitude=25&max_latitude=35&min_longitude=25&max_longitude=35&sensor=viirs"

curl "http://127.0.0.1:8000/api/v1/calendar?start_date=2025-10-01&end_date=2025-10-08&region_id=EGY"

curl "http://127.0.0.1:8000/api/v1/analytics/seasonal?start_date=2025-01-01&end_date=2025-12-31"

curl "http://127.0.0.1:8000/api/v1/analytics/comparison?start_date=2025-01-01&end_date=2025-12-31&group_by=season"

curl "http://127.0.0.1:8000/api/v1/analytics/anomalies?start_date=2025-01-01&end_date=2025-12-31"

curl -OJ "http://127.0.0.1:8000/api/v1/exports/fires?region_id=EGY"
```

Expected current-data behavior: the comparison and anomaly endpoints return
`insufficient_history` because only one year of data is present.

## Security and error handling

- Database credentials are held in `SecretStr` settings and are never returned
  in responses or logged.
- All user-supplied filter values are bound as asyncpg parameters. Only trusted,
  code-defined SQL fragments are interpolated.
- Central handlers map missing regions/detections to 404, invalid date ranges to
  422, database unavailability to 503, and unexpected query failures to a
  generic 500 response.
- CORS allows only `GET` and `OPTIONS`.
- Swagger/OpenAPI documentation is available at `/docs`.

## Pending database cleanup (NOT EXECUTED)

The empty scaffold tables `public.fire_detections` and `public.regions` are no
longer used by the API. Database-level checks found only the foreign key
`fire_detections.region_id → regions.id`, no dependent views, and no other
dependencies. Both tables contain zero rows.

The following statement is **proposed and has not been executed**. It requires
explicit approval before running:

```sql
DROP TABLE IF EXISTS public.fire_detections, public.regions;
```

Dropping these tables also drops their owned sequences
`fire_detections_id_seq` and `regions_id_seq`.

## Project structure

```text
backend/
├── app/
│   ├── main.py                 # app factory, lifespan, error handlers, CORS
│   ├── core/                   # settings, exceptions, optional export API key
│   ├── db/                     # asyncpg pool and query translation
│   ├── api/                    # versioned routes and dependency factories
│   ├── schemas/                # Pydantic v2 models
│   ├── repositories/           # parameterized raw SQL
│   ├── services/               # business logic and CSV streaming
│   └── utils/                  # confidence, seasons, statistics, CSV safety
├── tests/                      # mocked/unit tests, no production DB
├── .env.example
├── requirements.txt
└── README.md
```

## Known limitations

- The current dataset has only one year, so historical comparisons and anomaly
  scores cannot yet be produced. This is reported explicitly.
- The dataset contains only 35 rows, so the API is functionally verified but not
  load-tested.
- The derivation of country regions relies on populated `country_code` values.
- `public.fire_daily_counts` is not used and has no refresh trigger/schedule.
- No indexes were added. Existing `acq_date`, `country_code + acq_date`,
  `acq_datetime_utc`, GiST geometry, `spatial_grid_id`, and `year + month`
  indexes cover current filters; add a composite sensor/date index only after
  approval and query-plan review.
- The legacy scaffold tables remain until cleanup is approved.
