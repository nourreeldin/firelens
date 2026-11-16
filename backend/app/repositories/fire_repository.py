"""Parameterized raw-SQL access for fire detections."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.db.database import Database
from app.repositories.filters import build_fire_filters
from app.schemas.common import FireFilters

FIRE_SELECT_COLUMNS = """
    id,
    latitude,
    longitude,
    acq_date,
    acq_time,
    acq_datetime_utc,
    sensor,
    confidence,
    satellite,
    version,
    daynight,
    brightness,
    brightness_thermal,
    scan,
    track,
    frp,
    country_code,
    country_name,
    continent,
    spatial_grid_id,
    source_detection_id,
    coordinate_reference_system,
    bright_t31,
    bright_ti4,
    bright_ti5,
    source_file,
    instrument,
    fire_type,
    hour,
    minute,
    year,
    month,
    day,
    day_of_year,
    grid_lat,
    grid_lon,
    created_at
"""


class FireRepository:
    """Read-only detection queries against ``public.fire_hotspots``."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def list(
        self,
        filters: FireFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return one page of detections and the total matching count."""
        builder = build_fire_filters(filters)
        where_sql = builder.where_sql

        total_raw = await self.database.fetchval(
            f"SELECT COUNT(*) FROM public.fire_hotspots {where_sql}",
            *builder.params,
        )
        total = int(total_raw or 0)

        limit_position = len(builder.params) + 1
        offset_position = len(builder.params) + 2
        rows = await self.database.fetch(
            f"""
            SELECT {FIRE_SELECT_COLUMNS}
            FROM public.fire_hotspots
            {where_sql}
            ORDER BY acq_datetime_utc DESC NULLS LAST, id DESC
            LIMIT ${limit_position} OFFSET ${offset_position}
            """,
            *builder.params,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total

    async def get(self, fire_id: int) -> dict[str, Any] | None:
        """Return one detection by primary key."""
        row = await self.database.fetchrow(
            f"""
            SELECT {FIRE_SELECT_COLUMNS}
            FROM public.fire_hotspots
            WHERE id = $1
            """,
            fire_id,
        )
        return dict(row) if row is not None else None

    async def stream(
        self,
        filters: FireFilters,
        *,
        batch_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield matching detections without materializing the full result set."""
        builder = build_fire_filters(filters)
        query = f"""
            SELECT {FIRE_SELECT_COLUMNS}
            FROM public.fire_hotspots
            {builder.where_sql}
            ORDER BY acq_datetime_utc DESC NULLS LAST, id DESC
        """
        async with (
            self.database.acquire() as connection,
            connection.transaction(),
        ):
            cursor = connection.cursor(
                query,
                *builder.params,
                prefetch=batch_size,
            )
            async for row in cursor:
                yield dict(row)
