"""Regression coverage for the schema documented in SCHEMA.md."""

import csv
import io
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import Settings
from app.repositories.filters import build_fire_filters
from app.repositories.harmonization_repository import HarmonizationRepository
from app.schemas.activity import ActivityFilters
from app.schemas.common import FireFilters
from app.services.harmonization_service import HarmonizationService

METHOD = "daily-grid-modis-equivalent-v1"
QA_METHOD = "pair-integrity-1km-30min-v1"
DAY = date(2020, 7, 15)
TIMESTAMP = datetime(2020, 7, 15, 0, 32, tzinfo=timezone.utc)


@pytest.fixture
def database():
    return AsyncMock()


@pytest.fixture
async def client(database, monkeypatch):
    # Some developer shells set DEBUG=release, which is not an API boolean.
    monkeypatch.setenv("DEBUG", "false")
    from app.main import create_app

    app = create_app(Settings(_env_file=None, environment="testing", api_key=None))
    app.state.database = database
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.parametrize("raw", [None, "h", "085"])
async def test_fire_json_preserves_identifiers_native_bands_and_nulls(client, database, raw):
    database.fetchrow.return_value = {
        "id": 1, "latitude": 30.04, "longitude": 31.23, "acq_date": DAY,
        "source_detection_id": "EGY_2020_VIIRS_000000001", "sensor": "VIIRS",
        "acq_time": 32, "acq_datetime_utc": TIMESTAMP, "confidence": raw,
        "version": "002.00", "bright_t31": None, "bright_ti4": 333.25,
        "bright_ti5": 287.75, "source_file": None, "instrument": "VIIRS",
        "fire_type": None, "created_at": None,
    }
    response = await client.get("/api/v1/fires/1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_detection_id"] == "EGY_2020_VIIRS_000000001"
    assert payload["confidence_raw"] == raw
    assert payload["version"] == "002.00"
    assert payload["bright_ti4"] == 333.25
    assert payload["bright_ti5"] == 287.75
    for field in ("bright_t31", "source_file", "fire_type", "created_at", "frp"):
        assert payload[field] is None
    assert payload["acq_time"] == 32
    assert datetime.fromisoformat(payload["acq_datetime_utc"]).utcoffset().total_seconds() == 0
    query, fire_id = database.fetchrow.call_args.args
    assert "source_detection_id" in query
    assert "bright_t31" in query
    assert fire_id == 1


async def test_fire_list_uses_same_schema_fields(client, database):
    database.fetchval.return_value = 1
    database.fetch.return_value = [{
        "id": 1, "latitude": 1.0, "longitude": 2.0, "acq_date": DAY,
        "source_detection_id": None, "confidence": None,
    }]
    response = await client.get("/api/v1/fires")
    assert response.status_code == 200
    assert response.json()["data"][0]["source_detection_id"] is None
    assert response.json()["data"][0]["bright_t31"] is None


def test_bbox_retains_detections_with_null_geometry():
    filters = FireFilters(min_longitude=30, min_latitude=20,
                          max_longitude=35, max_latitude=33)
    builder = build_fire_filters(filters)
    assert "ST_Intersects(geom, ST_MakeEnvelope($1, $2, $3, $4, 4326))" in builder.where_sql
    assert "OR (geom IS NULL AND ST_Intersects(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)" in builder.where_sql
    assert "COALESCE(geom" not in builder.where_sql
    assert builder.params == [30, 20, 35, 33]


def test_bbox_grouping_and_parameter_offsets_with_other_filters():
    filters = FireFilters(start_date=DAY, end_date=DAY, region_id="EGY", sensor="VIIRS",
                          min_longitude=30, min_latitude=20,
                          max_longitude=35, max_latitude=33)
    builder = build_fire_filters(filters, param_offset=2)
    assert builder.params == [DAY, DAY, "EGY", "VIIRS", 30, 20, 35, 33]
    assert "sensor = $6 AND ((geom IS NOT NULL AND " in builder.where_sql
    assert builder.where_sql.count("ST_MakeEnvelope($7, $8, $9, $10, 4326)") == 2


@pytest.mark.parametrize("estimate", [None, 0.0, 5.819])
async def test_activity_json_retains_fractions_and_nullable_region(client, database, estimate):
    database.fetchval.return_value = 1
    database.fetch.return_value = [{
        "id": 1, "region_id": None, "country_code": None, "activity_date": DAY,
        "spatial_grid_id": None, "modis_count": 10, "viirs_count": 18,
        "harmonized_count": estimate, "correction_factor": None, "uncertainty": None,
        "method_version": METHOD, "created_at": TIMESTAMP,
    }]
    response = await client.get("/api/v1/harmonization", params={"method_version": METHOD})
    assert response.status_code == 200
    payload = response.json()["data"][0]
    assert payload["harmonized_count"] == estimate
    assert payload["region_id"] is None
    assert payload["country_code"] is None
    assert payload["uncertainty"] is None
    query, method, limit, offset = database.fetch.call_args.args
    assert "LEFT JOIN public.regions" in query
    assert METHOD not in query  # Passed as a bound value.
    assert (method, limit, offset) == (METHOD, 100, 0)


async def test_activity_without_method_includes_all_versions(client, database):
    database.fetchval.return_value = 0
    database.fetch.return_value = []
    response = await client.get("/api/v1/harmonization")
    assert response.status_code == 200
    assert database.fetchval.call_args.args[1:] == ()


async def test_calendar_response_alias_and_fractional_total(client, database):
    database.fetch.return_value = [{
        "date": DAY, "method_version": METHOD, "harmonized_activity": 1.1365,
        "modis_count": 2, "viirs_count": 3, "grid_records": 1, "uncertainty": 0.0045,
    }]
    response = await client.get("/api/v1/harmonization/calendar", params={
        "start_date": str(DAY), "end_date": str(DAY), "method_version": METHOD,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"][0]["date"] == str(DAY)
    assert payload["meta"]["total_harmonized_activity"] == 1.1365
    query, *args = database.fetch.call_args.args
    assert "days.day AS date" in query
    assert "COUNT(harmonized_count) = COUNT(*)" in query
    assert args == [DAY, DAY, DAY, DAY, METHOD]


@pytest.mark.parametrize("grid_records, expected", [(0, 1.1365), (1, None)])
async def test_calendar_total_distinguishes_gap_from_missing_estimate(database, grid_records, expected):
    database.fetch.return_value = [
        {"date": DAY, "method_version": METHOD, "harmonized_activity": 1.1365,
         "modis_count": 2, "viirs_count": 3, "grid_records": 1, "uncertainty": None},
        {"date": date(2020, 7, 16), "method_version": METHOD, "harmonized_activity": None,
         "modis_count": 0, "viirs_count": 0, "grid_records": grid_records, "uncertainty": None},
    ]
    service = HarmonizationService(HarmonizationRepository(database), AsyncMock(), Settings(_env_file=None, debug=False))
    result = await service.calendar(ActivityFilters(start_date=DAY, end_date=date(2020, 7, 16)))
    assert result.meta.total_harmonized_activity == expected


async def test_validation_qa_is_independent_of_activity_method(client, database):
    database.fetchval.return_value = 1
    database.fetch.return_value = [{
        "id": 1, "region_id": None, "country_code": None, "method_version": QA_METHOD,
        "validation_period_start": None, "validation_period_end": None,
        "mae": None, "rmse": None, "bias": None, "sample_size": None,
        "notes": None, "created_at": TIMESTAMP,
    }]
    response = await client.get("/api/v1/validation", params={"method_version": QA_METHOD})
    assert response.status_code == 200
    assert response.json()["data"][0]["mae"] is None
    assert response.json()["data"][0]["sample_size"] is None
    query, method, *_ = database.fetch.call_args.args
    assert method == QA_METHOD
    assert "LEFT JOIN public.regions" in query
    assert "harmonized_activity" not in query


async def test_catalog_nullable_created_timestamp(client, database):
    database.fetch.return_value = [{"id": 1, "name": "Egypt", "slug": "egypt", "created_at": None}]
    response = await client.get("/api/v1/regions/catalog")
    assert response.status_code == 200
    assert response.json()["data"][0]["created_at"] is None


async def test_fire_csv_includes_text_id_and_nullable_sensor_fields(client, database):
    # The cursor protocol is an async iterator, not an awaitable fetch call.
    from contextlib import asynccontextmanager
    from unittest.mock import Mock

    async def rows():
        yield {"id": 1, "source_detection_id": "EGY_001", "bright_t31": None,
               "bright_ti4": 333.25, "version": "002.00", "confidence": "h"}

    @asynccontextmanager
    async def context(value):
        yield value

    connection = Mock()
    connection.cursor.return_value = rows()
    connection.transaction.side_effect = lambda: context(None)
    database.acquire = lambda: context(connection)
    response = await client.get("/api/v1/exports/fires")
    assert response.status_code == 200
    record = next(csv.DictReader(io.StringIO(response.text)))
    assert record["source_detection_id"] == "EGY_001"
    assert record["bright_t31"] == ""
    assert record["bright_ti4"] == "333.25"
    assert record["version"] == "002.00"
