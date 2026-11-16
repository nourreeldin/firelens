# FireLens database schema

This is the backend reference for the `public` schema in FireLens Supabase (`nzkfnbxiondcoesjaatx`). Column types, nullability, defaults, keys, and row-level security were checked against the live database on 2026-11-15. The data notes describe the imported 2018–2020 study dataset.

## FastAPI integration

- Use schema-qualified table names in SQL and pass filters as query parameters. All seven tables have row-level security enabled. Use the backend’s configured database role and existing access rules.
- Model nullable columns as optional. Preserve missing values as `null` in API responses. Keep `date` fields as dates and serialize `timestamptz` values with a timezone. `acq_time` stores an integer HHMM, for example `32` means 00:32 UTC. Use `acq_datetime_utc` when a timestamp is needed.
- Use `LEFT JOIN public.regions` from activity or validation reports if the endpoint should retain rows with a missing region. The hotspot, event, and overlap tables store country labels and codes directly. These country fields have no region foreign key.
- Join event members and overlap pairs to `fire_hotspots.source_detection_id`. Keep the text identifiers in API responses. For maps, use `longitude`, `latitude` in that order for GeoJSON coordinates, or serialize `geom` explicitly. `geom` stores WGS 84 points in SRID 4326 and is nullable.
- Preserve raw confidence and version values as strings. `bright_t31` is the native MODIS thermal band, while `bright_ti4` and `bright_ti5` are native VIIRS bands. These sensor-specific fields may be null. FRP is in MW.

## Harmonized activity and validation

The populated activity method is `daily-grid-modis-equivalent-v1`. The 204,971 imported daily-grid rows now use this method. A backend filter hardcoded to `daily-grid-raw-counts-v1` will miss those rows. Raw observations remain available as `modis_count` and `viirs_count` on the same rows.

- `correction_factor` scales VIIRS detections to the MODIS scale. The fitted country factors are approximately **0.1544** for Algeria, **0.0910** for Egypt, and **0.2577** for South Africa. The factors were fitted on 2018–2019 country-days with detections from both sensors and evaluated against MODIS on held-out 2020 country-days.
- `harmonized_count = (modis_count + correction_factor × viirs_count) / 2`. This is a fractional hotspot detection index. Keep it as a float when exposing or aggregating it.
- `uncertainty = viirs_count × SE(correction_factor) / 2`, with the factor standard error estimated using month blocks. It covers variation in the estimated factor. It excludes coverage, cloud effects, missed detections, and grid-level predictive error. A zero VIIRS count gives zero contribution from factor uncertainty. Rows using the same country factor share that source of uncertainty, so avoid summing their uncertainties as independent errors.
- The existing `validation_reports` rows use `pair-integrity-1km-30min-v1`. They are candidate-pair QA summaries, and their sample sizes represent validated overlap pairs. Their nullable `mae`, `rmse`, and `bias` fields do not contain the 2020 calibration metrics. An API join on the activity `method_version` will therefore find no corresponding report in this imported dataset.

## Relationship map

| From | References |
|---|---|
| `harmonized_activity.region_id` | `regions.id` |
| `validation_reports.region_id` | `regions.id` |
| `fire_event_members.fire_event_id` | `fire_events.fire_event_id` |
| `fire_event_members.detection_id` | `fire_hotspots.source_detection_id` |
| `fire_overlap_pairs.detection_id_a` | `fire_hotspots.source_detection_id` |
| `fire_overlap_pairs.detection_id_b` | `fire_hotspots.source_detection_id` |

## Tables

### `public.regions`

One row per study region. `slug` is the unique lookup key. The stored bounds describe the detection dataset’s observed extent.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `id` | `int4` | No | Primary key · Identity by default |
| `name` | `character varying(255)` | No | — |
| `slug` | `character varying(255)` | No | Unique |
| `country_code` | `character varying(3)` | Yes | — |
| `description` | `text` | Yes | — |
| `min_latitude` | `float8` | Yes | — |
| `min_longitude` | `float8` | Yes | — |
| `max_latitude` | `float8` | Yes | — |
| `max_longitude` | `float8` | Yes | — |
| `created_at` | `timestamptz` | Yes | `now()` |

### `public.fire_hotspots`

One row per satellite hotspot detection. `id` is the database identity. `source_detection_id` is the unique text identifier used by event and overlap joins. The unique index permits multiple SQL `NULL` values.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `id` | `int8` | No | Primary key · Identity by default |
| `latitude` | `float8` | No | — |
| `longitude` | `float8` | No | — |
| `geom` | `geometry(Point,4326)` | Yes | — |
| `coordinate_reference_system` | `text` | Yes | — |
| `brightness` | `float8` | Yes | — |
| `brightness_thermal` | `float8` | Yes | — |
| `scan` | `float8` | Yes | — |
| `track` | `float8` | Yes | — |
| `frp` | `float8` | Yes | — |
| `acq_date` | `date` | No | — |
| `acq_time` | `int4` | Yes | — |
| `acq_datetime_utc` | `timestamptz` | Yes | — |
| `hour` | `int2` | Yes | — |
| `minute` | `int2` | Yes | — |
| `year` | `int2` | Yes | — |
| `month` | `int2` | Yes | — |
| `day` | `int2` | Yes | — |
| `day_of_year` | `int2` | Yes | — |
| `satellite` | `text` | Yes | — |
| `sensor` | `text` | Yes | — |
| `confidence` | `text` | Yes | — |
| `version` | `text` | Yes | — |
| `daynight` | `text` | Yes | — |
| `grid_lat` | `int4` | Yes | — |
| `grid_lon` | `int4` | Yes | — |
| `spatial_grid_id` | `text` | Yes | — |
| `country_name` | `text` | Yes | — |
| `country_code` | `text` | Yes | — |
| `continent` | `text` | Yes | — |
| `created_at` | `timestamptz` | Yes | `now()` |
| `source_detection_id` | `text` | Yes | Unique index |
| `bright_t31` | `float8` | Yes | — |
| `bright_ti4` | `float8` | Yes | — |
| `bright_ti5` | `float8` | Yes | — |
| `source_file` | `text` | Yes | — |
| `instrument` | `text` | Yes | — |
| `fire_type` | `int4` | Yes | — |

### `public.harmonized_activity`

One activity row per region, UTC date, spatial grid, and method version. The unique index on `(region_id, activity_date, spatial_grid_id, method_version)` uses `NULLS NOT DISTINCT`.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `id` | `int8` | No | Primary key · Identity always |
| `region_id` | `int4` | Yes | FK → `regions.id` · on delete set null |
| `activity_date` | `date` | No | — |
| `spatial_grid_id` | `text` | Yes | — |
| `modis_count` | `int4` | No | `0` |
| `viirs_count` | `int4` | No | `0` |
| `harmonized_count` | `float8` | Yes | — |
| `correction_factor` | `float8` | Yes | — |
| `uncertainty` | `float8` | Yes | — |
| `method_version` | `text` | No | `'v1'::text` |
| `created_at` | `timestamptz` | No | `now()` |

Raw counts are nonnegative. The harmonized count and uncertainty are nonnegative when present.

### `public.validation_reports`

One report per region, method, and validation period when all key fields are present. The unique index on `(region_id, method_version, validation_period_start, validation_period_end)` uses PostgreSQL’s default NULL behavior.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `id` | `int8` | No | Primary key · Identity always |
| `region_id` | `int4` | Yes | FK → `regions.id` · on delete set null |
| `method_version` | `text` | No | — |
| `validation_period_start` | `date` | Yes | — |
| `validation_period_end` | `date` | Yes | — |
| `mae` | `float8` | Yes | — |
| `rmse` | `float8` | Yes | — |
| `bias` | `float8` | Yes | — |
| `sample_size` | `int4` | Yes | — |
| `notes` | `text` | Yes | — |
| `created_at` | `timestamptz` | No | `now()` |

MAE, RMSE, and sample size are nonnegative when present. If both dates are present, the start date must be on or before the end date.

### `public.fire_events`

One row per candidate event derived from matched hotspots. `requires_review` flags candidate events needing review.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `fire_event_id` | `text` | No | Primary key |
| `country_name` | `text` | No | — |
| `country_code` | `text` | No | — |
| `year` | `int2` | No | — |
| `detection_count` | `int4` | No | — |
| `modis_count` | `int4` | No | — |
| `viirs_count` | `int4` | No | — |
| `start_time_utc` | `timestamptz` | No | — |
| `end_time_utc` | `timestamptz` | No | — |
| `latitude_min` | `float8` | No | — |
| `latitude_max` | `float8` | No | — |
| `longitude_min` | `float8` | No | — |
| `longitude_max` | `float8` | No | — |
| `centroid_latitude` | `float8` | No | — |
| `centroid_longitude` | `float8` | No | — |
| `mean_frp` | `float8` | Yes | — |
| `max_frp` | `float8` | Yes | — |
| `duration_minutes` | `float8` | No | — |
| `bbox_diagonal_meters` | `float8` | Yes | — |
| `matching_pair_count` | `int4` | No | — |
| `multi_sensor` | `bool` | No | — |
| `duration_review_flag` | `bool` | No | — |
| `spatial_review_flag` | `bool` | No | — |
| `requires_review` | `bool` | No | — |
| `created_at` | `timestamptz` | No | `now()` |

### `public.fire_event_members`

One event assignment per member detection. The primary key on `detection_id` allows each detection to belong to at most one event in this table.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `detection_id` | `text` | No | Primary key · FK → `fire_hotspots.source_detection_id` |
| `fire_event_id` | `text` | No | FK → `fire_events.fire_event_id` |
| `created_at` | `timestamptz` | No | `now()` |

### `public.fire_overlap_pairs`

One row per ordered detection pair. The primary key is composite. In the imported dataset, side A is MODIS and side B is VIIRS.

| Column | PostgreSQL type | Nullable | Key or default |
|---|---|---|---|
| `detection_id_a` | `text` | No | Part of composite primary key · FK → `fire_hotspots.source_detection_id` |
| `detection_id_b` | `text` | No | Part of composite primary key · FK → `fire_hotspots.source_detection_id` |
| `sensor_a` | `text` | No | — |
| `sensor_b` | `text` | No | — |
| `country_name` | `text` | No | — |
| `country_code` | `text` | No | — |
| `year` | `int2` | No | — |
| `distance_meters` | `float8` | No | — |
| `time_difference_minutes` | `float8` | No | — |
| `spatial_match` | `bool` | No | — |
| `temporal_match` | `bool` | No | — |
| `created_at` | `timestamptz` | No | `now()` |

Database checks allow distances from 0 to 1000.000001 m and time differences from 0 to 30.000001 minutes.
