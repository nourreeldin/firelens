# FireLens

**One view of fire activity. Powered by NASA satellite data.**

FireLens is a geospatial platform for exploring active-fire observations from NASA's MODIS and VIIRS instruments. It combines a Python data-processing pipeline, a FastAPI backend for querying fire and harmonized-activity datasets, and a Next.js dashboard for map, calendar, analytics, and validation workflows.

> **Project status:** Prototype developed for NASA Space Apps Cairo 2026. Functionality, data coverage, and deployment details depend on the configured dataset and environment.

## Repository structure

```text
.
├── frontend/   # Next.js dashboard and landing page
├── backend/    # FastAPI read-only API (PostgreSQL + PostGIS)
├── engine/     # Python scripts for harmonization, matching, and validation
├── DESIGN.md   # UI/design reference notes
└── README.md
```

## What’s in this repository

### Frontend (`frontend/`)

A Next.js (App Router) application that provides:

- A landing page with project context and entry points to the dashboard.
- Dashboard workspaces for overview, fire activity, map, detection records, historical analytics, harmonization, and validation views.
- Client data fetching with TanStack Query and visualization with React Leaflet and Recharts.
- Browser-to-backend proxy routes for JSON and CSV export requests, so the frontend can talk to the FireLens API without depending on backend CORS for browser fetches.

See [`frontend/README.md`](frontend/README.md) for local development, environment variables, map tile configuration, and frontend-specific behavior.

### Backend (`backend/`)

A read-only FastAPI service (v1 under `/api/v1`) backed by PostgreSQL/PostGIS via asyncpg. It exposes:

- Raw fire detections, regions, calendar, seasonal/comparison/anomaly analytics, and CSV exports.
- Harmonized activity records and analytics (separate from raw detection counts).
- Validation reports and exports.
- Health checks and OpenAPI/Swagger documentation (`/docs`, `/redoc`).

The backend uses parameterized SQL, does not create or alter database objects at startup, and requires an existing `DATABASE_URL` pointing to a compatible database.

See [`backend/README.md`](backend/README.md) and [`backend/API.md`](backend/API.md) for setup, routes, data model notes, and API details.

### Engine (`engine/`)

Python scripts for preparing and validating fire-detection datasets, including:

- Harmonization of MODIS/VIIRS inputs.
- Validation of harmonized records.
- Spatial-temporal overlap/matching between sensors.
- Match validation and fire-event grouping utilities.

The engine expects raw/processed data in `engine/data/` (ignored by `engine/.gitignore`) and is typically run from the `engine/` directory.

See [`engine/README.md`](engine/README.md) for script order, dependencies, and expected outputs.

## Getting started

### Prerequisites

- **Frontend:** Node.js and [pnpm](https://pnpm.io/) (the app declares `pnpm@12.3.4` in `frontend/package.json`).
- **Backend:** Python 3.12+, access to PostgreSQL 15+ with PostGIS, and a valid `DATABASE_URL`.
- **Engine:** Python 3.x and dependencies from `engine/requirements.txt`.

### 1. Run the backend

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
cp .env.example .env
# Set DATABASE_URL in .env
uvicorn app.main:app --reload
```

Default local URLs:
- API: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`

### 2. Run the frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_BASE_URL (and optional vars as needed)
pnpm dev
```

Open `http://localhost:3000`. The landing page links to the dashboard at `/dashboard`.

### 3. Run engine scripts (optional/data workflow)

```bash
cd engine
pip install -r requirements.txt
# Place or prepare input data under engine/data/ as expected by the scripts
python scripts/harmonization.py
python scripts/validate_harmonized.py
python scripts/overlap_detection.py
python scripts/validate_matching.py
python scripts/fire_event_grouping.py
```

Script paths, thresholds, and outputs are defined/configured within the engine scripts and documented in [`engine/README.md`](engine/README.md).

## Configuration notes

- Do not commit secrets. Use environment files such as `backend/.env` and `frontend/.env.local`.
- Frontend browser requests can be proxied through Next.js routes; server-side export proxying can use `FIRELENS_API_BASE_URL` and `FIRELENS_API_KEY` when required by the backend.
- Backend analytics behavior (date coverage, historical/anomaly availability, method versions) depends on the data loaded in the connected database.
- Treat satellite detections as observations, not confirmed fire perimeters. Interpretation should account for sensor characteristics, overpass timing, and environmental conditions.

## Data sources & attribution

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) — Fire Information for Resource Management System (MODIS and VIIRS active-fire data).
- [FIRMS API documentation](https://firms.modaps.eosdis.nasa.gov/api/)
- [NASA Earthdata](https://www.earthdata.nasa.gov/)

Follow applicable NASA data-use guidance and include appropriate attribution when presenting derived outputs. FireLens is an independent project and not an official NASA product.

## Team Supernova-X

| Member | Role |
| --- | --- |
| Noureldin Hossam | Team Leader · Full-Stack Developer · System Architect |
| Ahmed Badr | Backend Developer |
| Youssef Ahmed | Data Engineer |
| Nader Sherif | Data Engineer |
| Mohamed Sherif | Data Scientist |
| Yara Ibrahim | Data Scientist · Storyteller |

Built for **NASA Space Apps Challenge 2026 — Cairo Local Event**.

