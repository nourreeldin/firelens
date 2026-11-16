# FireLens map bounds benchmark

Measured 2026-11-15, 21:18–21:20 UTC (23:18–23:20 Cairo).

The split predicate used `idx_fire_hotspots_geom` in every recorded after plan.
Results were identical, but end-to-end performance was mixed: narrow South
Africa improved 27.4%, Egypt was effectively unchanged, and the wider South
Africa view regressed 16.3%. These measurements do not support an unconditional
performance rollout. No database migration or new index is needed for this
query change; the existing GiST index is already present.

## Exact requests and matching results

All requests used `GET /api/v1/fires`, `start_date=2020-01-01`,
`end_date=2020-12-31`, `limit=100`, and `offset=0`. Dates are inclusive.
Bounds below are `(min_longitude, min_latitude, max_longitude, max_latitude)`.

| Case | Bounds | Country filter | Sensor filter | Matching rows, before = after |
| --- | --- | --- | --- | ---: |
| Egypt narrow | `(30.8, 29.8, 31.8, 30.8)` | `region_id=EGY` | `sensor=VIIRS` | 1,052 |
| South Africa narrow | `(28, -29, 29, -28)` | `region_id=ZAF` | `sensor=VIIRS` | 1,784 |
| South Africa wide | `(16, -35, 33, -22)` | `region_id=ZAF` | Omitted: both sensors | 173,662 |

For example, the wide request was:

```text
/api/v1/fires?start_date=2020-01-01&end_date=2020-12-31&region_id=ZAF&min_longitude=16&min_latitude=-35&max_longitude=33&max_latitude=-22&limit=100&offset=0
```

Bidirectional `EXCEPT` compared the complete matching ID sets within the same
repeatable-read snapshot for each case: zero IDs appeared only before or only
after. Every HTTP response also matched as a complete JSON payload, including
the ordered 100-row page, field values, and pagination total.

## Median API response times

| Case | Before | After | Change, after minus before | Relative change |
| --- | ---: | ---: | ---: | ---: |
| Egypt narrow | 830.85 ms | 829.51 ms | -1.35 ms | -0.2% |
| South Africa narrow | 1,074.40 ms | 780.44 ms | -293.96 ms | -27.4% |
| South Africa wide, both sensors | 1,626.42 ms | 1,891.52 ms | +265.10 ms | +16.3% |

Each number is the median of **nine timed requests per version per case**, after
two untimed warm-ups per version. Before/after order alternated every round.
No samples were discarded. A temporary Uvicorn server accepted real loopback
HTTP requests from a reused HTTPX connection. The normal routes, dependencies,
repositories, Pydantic serialization, region validation, matching-count query,
and page query ran against the configured remote database. The temporary server
was stopped after the run; an existing development server was not modified.

These are single-client, warm-cache local API measurements including remote
database latency, not production throughput or browser-network benchmarks.
Egypt's 1.35 ms change is small compared with the observed request variation
(before 722–894 ms; after 713–1,037 ms), so it is not a meaningful API improvement.

## EXPLAIN (ANALYZE, BUFFERS)

The benchmark explained the **actual matching-count SQL and full-field,
ordered, paginated SELECT** used by the endpoint. Each query/version/case ran
three times with alternating version order. The table contains medians, in ms.

| Case | Query | Before execution | After execution | Before shared hits | After shared hits | Spatial index before → after |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Egypt narrow | Count | 54.786 | 14.177 | 553 | 3,814 | No → Yes |
| Egypt narrow | Page | 58.072 | 15.559 | 553 | 3,814 | No → Yes |
| South Africa narrow | Count | 574.315 | 232.862 | 9,379 | 4,079 | No → Yes |
| South Africa narrow | Page | 324.257 | 116.226 | 9,399 | 4,094 | No → Yes |
| South Africa wide | Count | 199.022 | 269.713 | 8,079 | 13,788 | No → Yes |
| South Africa wide | Page | 393.607 | 432.822 | 8,120 | 13,803 | No → Yes |

All recorded plans had zero shared blocks read from storage. Shared hits are
buffer accesses, not distinct pages. No planner options were changed to force
index use: `enable_seqscan=on`, `enable_bitmapscan=on`, `plan_cache_mode=auto`.
The database reported PostgreSQL 17.11.

Before plans used `idx_fire_hotspots_country_date` for Egypt and wide South
Africa, and `idx_fire_hotspots_sensor_date` for narrow South Africa. They did not
use `idx_fire_hotspots_geom`. After plans used `Bitmap Index Scan` on
`idx_fire_hotspots_geom`, combined through `BitmapOr` and `BitmapAnd` with the
same country/date or sensor/date index. This was true for all three repetitions
of each count and page query.

The broad view matches 173,662 rows. Its additional bitmap/index work and higher
shared-buffer accesses are consistent with the measured regression; this is an
inference from the plans, not proof that spatial index use benefits every map
view. A wide viewport can gain little selectivity from a spatial index.

These EXPLAIN executions and HTTP timings are separate measurements. SQL
execution medians do not include database round trips or API work, and the
medians of individual queries should not be added to predict the HTTP median.
The normal automatic prepared-statement plan policy remained enabled.

## Missing-geometry fallback verification

The live table had **648,568 rows and zero rows with `geom IS NULL`** at the time
of measurement. Live ID equality therefore cannot, on its own, prove the null
fallback. A separate read-only `VALUES` CTE exercised ten synthetic rows using
both predicates and the Egypt filters above. It created no database objects and
inserted no rows.

Both predicates returned exactly `[1, 2, 3, 4, 9]`, including three null-geometry
rows inside or exactly on the bounds. Checks covered:

- Null geometry inside the rectangle and on both inclusive corner boundaries.
- Null geometry outside the rectangle.
- Null geometry inside the rectangle but excluded by country, date, or sensor.
- Non-null geometry inside with stored longitude/latitude outside: geometry wins.
- Non-null geometry outside with stored longitude/latitude inside: excluded.

This verifies logical fallback equivalence separately; it does not measure the
performance of a future dataset with many missing geometries.

## Code and reproduction

`app/repositories/filters.py` now builds a parenthesized OR:

```sql
((geom IS NOT NULL AND
  ST_Intersects(geom, ST_MakeEnvelope($west, $south, $east, $north, 4326)))
 OR
 (geom IS NULL AND
  ST_Intersects(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                ST_MakeEnvelope($west, $south, $east, $north, 4326))))
```

The real SQL uses numbered bound parameters; the same four bounds are reused
in both branches. The complete OR is ANDed with date, country, and sensor
conditions. The prior `COALESCE` predicate is frozen in the benchmark's
`before_filters` function, sharing the unchanged common-filter construction.

From `backend` with its environment active:

```bash
python -m benchmarks.map_bounds
FIRELENS_LIVE_TESTS=1 python -m pytest -q -p no:cacheprovider
```

The benchmark issues only SELECT/EXPLAIN queries and does not change data,
indexes, schema, statistics, or planner settings. Its results directory contains
[all measurements](results.json) and 36 complete JSON EXPLAIN plans, named by
case, version, query, and repetition. Re-running overwrites those artifacts.

PostGIS documents the index-aware bounding-box comparison performed by
[ST_Intersects](https://postgis.net/docs/ST_Intersects.html). PostgreSQL documents
[combining index scans with bitmaps](https://www.postgresql.org/docs/current/indexes-bitmap-scans.html).

For the current workload, keep the wide-view regression in the migration
decision. The selective South Africa improvement is real in this run, but the
change is not a general latency improvement. Validate a broader viewport mix
and production-like concurrency before a full rollout.
