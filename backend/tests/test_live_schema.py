"""Opt-in read-only checks against the backend's configured database.

Run with FIRELENS_LIVE_TESTS=1. Never creates or modifies database objects.
"""

import os

import asyncpg
import pytest

from app.core.config import Settings
from app.db.database import Database
from app.repositories.fire_repository import FireRepository
from app.repositories.harmonization_repository import HarmonizationRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.validation_repository import ValidationRepository
from app.schemas.activity import ActivityFilters, ActivityRecord
from app.schemas.region import RegionCatalogRecord
from app.schemas.validation import ValidationFilters, ValidationRecord
from app.services.fire_service import FireService
from app.services.harmonization_service import HarmonizationService

pytestmark = pytest.mark.skipif(
    os.environ.get("FIRELENS_LIVE_TESTS") != "1",
    reason="Set FIRELENS_LIVE_TESTS=1 to query the configured database read-only",
)


async def test_repository_queries_against_live_schema():
    settings = Settings(debug=False)
    pool = await asyncpg.create_pool(
        dsn=settings.database_dsn, min_size=1, max_size=1, timeout=10,
        command_timeout=30, server_settings={"default_transaction_read_only": "on"},
    )
    database = Database(pool)
    try:
        from benchmarks.map_bounds import check_fallback

        await check_fallback(pool)
        regions = RegionRepository(database)
        catalog = await regions.list_catalog()
        assert catalog
        for row in catalog:
            RegionCatalogRecord(**row)

        fires = FireRepository(database)
        fire_id = await database.fetchval("SELECT id FROM public.fire_hotspots LIMIT 1")
        record = FireService._to_record(await fires.get(fire_id))
        assert record.source_detection_id is None or isinstance(record.source_detection_id, str)

        activity = HarmonizationRepository(database)
        filters = ActivityFilters(method_version="daily-grid-modis-equivalent-v1")
        first, latest = await activity.date_bounds(filters)
        assert first is not None and latest is not None
        scoped = filters.model_copy(update={"start_date": latest, "end_date": latest})
        rows, total = await activity.list(scoped, limit=2, offset=0)
        assert total > 0
        for row in rows:
            ActivityRecord(**row)
        calendar = await HarmonizationService(activity, regions, settings).calendar(scoped)
        assert calendar.status == "ok"
        assert calendar.data[0].date == latest
        assert calendar.data[0].harmonized_activity is not None
        # Exercise the actual aggregate SQL with nullable fixture rows, without
        # changing live data. A partial day must not appear to be a complete sum.
        class FixtureDatabase:
            async def fetch(self, query, *args):
                fixture = """WITH activity_fixture AS (
                    SELECT * FROM (VALUES
                        ('2020-07-15'::date, 'fixture', 2, 3, 1.1365::float8, 0.0045::float8),
                        ('2020-07-16'::date, 'fixture', 2, 3, 1.1365::float8, 0.0045::float8),
                        ('2020-07-16'::date, 'fixture', 1, 2, NULL::float8, NULL::float8)
                    ) AS rows(activity_date, method_version, modis_count,
                              viirs_count, harmonized_count, uncertainty)
                ), """
                query = query.replace("public.harmonized_activity", "activity_fixture")
                return await database.fetch(fixture + query.lstrip().removeprefix("WITH"), *args)

        from datetime import date

        nullable_days = await HarmonizationRepository(FixtureDatabase()).daily_calendar(
            ActivityFilters(), start=date(2020, 7, 15), end=date(2020, 7, 17),
        )
        assert nullable_days[0]["harmonized_activity"] == 1.1365
        assert nullable_days[0]["uncertainty"] == 0.0045
        assert nullable_days[1]["harmonized_activity"] is None
        assert nullable_days[1]["uncertainty"] is None
        assert nullable_days[1]["modis_count"] == 3
        assert nullable_days[2]["grid_records"] == 0
        assert nullable_days[2]["harmonized_activity"] is None
        seasonal = await HarmonizationService(activity, regions, settings).seasonal(scoped)
        assert seasonal.status == "ok"

        reports, total = await ValidationRepository(database).list(
            ValidationFilters(method_version="pair-integrity-1km-30min-v1"),
            limit=2, offset=0,
        )
        assert total > 0
        for row in reports:
            ValidationRecord(**row)

        # These text keys are deliberately distinct from the numeric hotspot id.
        assert await database.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM public.fire_event_members AS members
                JOIN public.fire_hotspots AS hotspots
                  ON hotspots.source_detection_id = members.detection_id
                JOIN public.fire_events AS events
                  ON events.fire_event_id = members.fire_event_id
            )
        """)
        assert await database.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM public.fire_overlap_pairs AS pairs
                JOIN public.fire_hotspots AS a
                  ON a.source_detection_id = pairs.detection_id_a
                JOIN public.fire_hotspots AS b
                  ON b.source_detection_id = pairs.detection_id_b
            )
        """)
    finally:
        await pool.close()
