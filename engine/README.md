# FireLens Engine

Python scripts for processing NASA MODIS/VIIRS active fire datasets (South Africa, Egypt, Algeria; 2018–2020). The pipeline harmonizes raw CSV inputs, validates data quality, matches detections across sensors (spatial–temporal), validates matches, and groups matched detections into candidate fire events.

> Note: This README ignores the `data/` directory contents and focuses on scripts, setup, and expected script outputs.

## Repository layout

```
engine/
  scripts/
    harmonization.py        # Combine raw MODIS/VIIRS CSVs into one harmonized dataset
    validate_harmonized.py  # Validate harmonized dataset and export validation reports
    overlap_detection.py    # Match MODIS↔VIIRS detections (distance/time thresholds)
    validate_matching.py    # Recompute + validate match pairs; export validated/invalid sets
    fire_event_grouping.py  # Build fire-event groups from validated pairs (graph/union-find)
    check_columns.py        # Inspect CSV columns under data/raw
    analyze.py              # Example analysis/plots for a specific cleaned MODIS CSV
  requirements.txt
```

## Setup

- Python 3.x recommended.
- Install dependencies:

```bash
pip install -r requirements.txt
```

Main packages used: `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`, `geopandas` (some workflows like shapefile-based steps may require additional system/GDAL dependencies).

## Typical pipeline order

Run from the `engine` directory (scripts resolve paths relative to the project root):

1. `python scripts/harmonization.py`
2. `python scripts/validate_harmonized.py`
3. `python scripts/overlap_detection.py`
4. `python scripts/validate_matching.py`
5. `python scripts/fire_event_grouping.py`

## Expected outputs (by script)

### `scripts/harmonization.py`
- **Console output:** loading messages per input file, counts before/after validation, observations by country/year/sensor, final column list, and a success/failure banner.
- **Expected written artifacts (typical):** a combined harmonized CSV (e.g. under a harmonized output folder) containing standardized fields such as `detection_id`, `country_name/country_code`, `year`, `sensor`, `source_file`, `latitude/longitude`, and UTC timestamps.

### `scripts/validate_harmonized.py`
- **Console output:** column checks, data quality checks (coordinates/timestamps/IDs/country/year/sensor/instrument consistency), distribution summaries, and final pass/fail summary (plus counts of invalid observations).
- **Expected written artifacts (typical):** validation summary CSV(s), observations-by-group CSV, and an invalid observations CSV/report files in a validation output location.

### `scripts/overlap_detection.py`
- **Console output:** load summary, sensor distribution, per country/year matching progress, thresholds used (default behavior in script: ~1000 m, ~30 minutes), and final pair counts/summary.
- **Expected written artifacts (typical):** overlap/matching pair CSV and a matching summary CSV written to the script’s configured output location.

### `scripts/validate_matching.py`
- **Console output:** loaded counts, recalculation/validation steps, per-check pass/fail/warning summaries, and final totals (original/validated/excluded pairs).
- **Expected written artifacts (typical):** validated pairs CSV, invalid/excluded pairs CSV, matching validation summary CSV, and a matching distribution CSV in the validation output location.

### `scripts/fire_event_grouping.py`
- **Console output:** load/graph build messages, counts of matched detections/components, validation checks, and a final grouping summary (including review flags).
- **Expected written artifacts (typical):** fire event members CSV, fire event summary CSV, and a fire event validation CSV in the fire-events output location.

### `scripts/check_columns.py`
- **Console output:** lists discovered CSV files under `data/raw`, prints columns and a small sample per file (or errors if files are missing/unreadable).

### `scripts/analyze.py`
- **Console output:** dataset info/head/cleaning steps, summaries, and validation prints (depends on the configured input file).
- **Expected behavior:** may generate plots (matplotlib/seaborn) and can write a cleaned/aligned CSV depending on its current configuration (paths inside the script).

## Notes

- Thresholds and review flags are defined as constants near the top of the relevant scripts (e.g. matching distance/time, event review thresholds).
- Run scripts from the `engine` directory so relative paths resolve correctly.
- `analyze.py` is an example exploratory workflow and may require local input files/shapefiles configured inside the script.