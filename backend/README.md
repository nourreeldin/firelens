<p><img src="app/static/firelens-wordmark.svg" alt="FireLens - Earth observation" width="253" height="64" /></p>

# FireLens Backend

Read-only FastAPI service for exploring standardized raw **MODIS** and **VIIRS**
detections and their separate harmonized activity estimates from NASA FIRMS.
The API uses **parameterized raw SQL** through an asyncpg connection pool
against Supabase PostgreSQL + PostGIS. There is no ORM and the API never creates
or alters database objects.

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

`public.fire_hotspots` stores standardized raw satellite observations served by
the existing fire, calendar, analytics, and export endpoints. It retains
sensor-specific values such as `sensor` and `confidence`; those records are not
the corrected activity estimates produced by the harmonization method.

The database migration at
[`../supabase/migrations/20261114000000_firelens_activity_schema.sql`](../supabase/migrations/20261114000000_firelens_activity_schema.sql)
adds `public.harmonized_activity` and `public.validation_reports`, and extends
the existing `regions` table while preserving its integer IDs. The migration
also adds missing hotspot metadata columns and indexes. It is not run by the
FastAPI application. It has been applied to the database configured by this
workspace's `DATABASE_URL`; other environments must apply it separately before
using the new routes.

- Important `fire_hotspots` fields include `latitude`, `longitude`, `geom`,
  `acq_date`, `acq_time`, `acq_datetime_utc`, `sensor`, `confidence`,
  `satellite`, `country_code`, `country_name`, `continent`, and
  `spatial_grid_id`.
- `harmonized_activity` stores region/grid/day/method activity, source counts,
  corrected counts, correction factors, and uncertainty.
- `validation_reports` stores method-version metrics and their validation
  periods. Metrics remain nullable until calculated.
- `/api/v1/regions` still derives country filters from `fire_hotspots`; it does
  not query the `regions` table.
- `/api/v1/regions/catalog` returns the persisted integer-ID rows used by
  harmonized and validation records.

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
| `GET` | `/api/v1/regions/catalog` | Persisted integer-ID region catalog |
| `GET` | `/api/v1/calendar` | Zero-filled raw detection counts |
| `GET` | `/api/v1/analytics/seasonal` | Raw monthly and hemisphere-aware seasonal totals |
| `GET` | `/api/v1/analytics/comparison` | Raw detections vs prior-year baselines |
| `GET` | `/api/v1/analytics/anomalies` | Raw detection median/MAD anomalies |
| `GET` | `/api/v1/harmonization` | Paginated corrected activity records |
| `GET` | `/api/v1/harmonization/calendar` | Daily corrected activity and sensor counts |
| `GET` | `/api/v1/harmonization/analytics/seasonal` | Corrected monthly and season-code totals |
| `GET` | `/api/v1/harmonization/analytics/comparison` | Corrected monthly totals vs prior years |
| `GET` | `/api/v1/harmonization/analytics/anomalies` | Corrected monthly median/MAD anomalies |
| `GET` | `/api/v1/validation` | Paginated validation reports |
| `GET` | `/api/v1/exports/fires` | Streamed CSV export |
| `GET` | `/api/v1/exports/harmonization` | Streamed corrected activity CSV |
| `GET` | `/api/v1/exports/validation` | Streamed validation CSV |

The complete request and response reference is in [`API.md`](API.md). The raw
calendar and analytics endpoints keep their existing response contracts and
continue to count rows in `fire_hotspots`.

Unversioned `/health` and `/health/ready` aliases remain available for container
platforms and are excluded from the OpenAPI schema. There are no POST, PUT,
PATCH, or DELETE endpoints.

### Shared filters

Raw detection routes `/api/v1/fires`, `/calendar`, all top-level analytics
routes, and `/exports/fires` accept:

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

`/api/v1/regions/catalog` separately returns `id`, `name`, `slug`,
`country_code`, description, and optional bounds from `public.regions`. Use
`region_pk` (an integer) with harmonization and validation endpoints. Keep
`region_id` as the three-letter country-code parameter on raw-fire endpoints.

### Calendar

`/api/v1/calendar` remains detection-based and returns `fire_count` from
`public.fire_hotspots`.

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

`/api/v1/analytics/anomalies` remains detection-based and counts rows in
`public.fire_hotspots`.

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

The harmonization and validation CSV exports also stream through asyncpg
server-side cursors. They use the same formula-injection protection and API-key
requirement.

### Harmonized activity and validation

`GET /api/v1/harmonization` returns the stored rows from
`public.harmonized_activity` in a `{status, data, pagination}` envelope. It
supports `start_date`, `end_date`, `region_pk`, `spatial_grid_id`,
`method_version`, `limit`, and `offset`. `region_pk` is the integer
`public.regions.id`; it does not change the raw endpoints' country-code
`region_id` parameter.

`GET /api/v1/harmonization/calendar` supports the same activity filters and
returns one day per method version. It sums harmonized activity and MODIS/VIIRS
counts across matching grid records. It returns a stored uncertainty only if
the grouped day contains one grid record; multi-grid uncertainty is `null`
until the data science team defines a scientifically appropriate aggregation.
When dates are omitted it uses the latest 30 days in the filtered activity
data, subject to `MAX_CALENDAR_DAYS`.

Harmonized seasonal, comparison, and anomaly analytics live under
`/api/v1/harmonization/analytics/`. They do not replace the raw analytics. The
seasonal endpoint returns `DJF`, `MAM`, `JJA`, and `SON` codes without
hemisphere-specific labels because `harmonized_activity` has no latitude
column. Comparison and anomaly baselines stay separate by `method_version`;
they require a single calendar-year observation period. Historical mean,
median, and anomaly scores remain unavailable until the configured minimum
number of prior years is present.

`GET /api/v1/validation` returns paginated reports from
`public.validation_reports`. It accepts `region_pk`, `method_version`,
`start_date`, and `end_date`; dates select report periods that overlap the
requested interval. Nullable metrics remain `null` until calculated.

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

curl "http://127.0.0.1:8000/api/v1/harmonization?start_date=2025-07-01&end_date=2025-07-31&region_pk=1&method_version=v1&limit=50"

curl "http://127.0.0.1:8000/api/v1/harmonization/calendar?start_date=2025-07-01&end_date=2025-07-31&region_pk=1&method_version=v1"

curl "http://127.0.0.1:8000/api/v1/harmonization/analytics/comparison?start_date=2025-01-01&end_date=2025-12-31&region_pk=1&method_version=v1"

curl "http://127.0.0.1:8000/api/v1/validation?region_pk=1&method_version=v1&limit=25"

curl -OJ "http://127.0.0.1:8000/api/v1/exports/harmonization?region_pk=1&method_version=v1"
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

## Database rollout and legacy tables

The migration in `../supabase/migrations/` has been applied to the database
configured by this workspace's `DATABASE_URL`. It is not executed by the API at
startup, so other environments must apply it before using the harmonization and
validation endpoints. It preserves `fire_hotspots` rows and existing integer
region IDs.

Keep `public.fire_detections` until ingestion and processing jobs outside this
API have also been checked for dependencies. The API does not read it, but that
alone does not establish that no external job uses it. `public.regions` is
retained because harmonized activity and validation records reference its IDs.

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
- The API does not apply schema changes at startup. The migration adds indexes
  for hotspot date, country/date, sensor/date, grid/date, and geometry queries;
  review the target database's current indexes before applying it to avoid
  redundant indexes.
- The legacy `fire_detections` scaffold table remains until cleanup is
  approved. The `regions` table is retained for harmonized data references.
