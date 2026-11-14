"""Parameterized raw-SQL access for dynamically derived country regions."""

from __future__ import annotations

from typing import Any

from app.db.database import Database

REGION_AGGREGATE_SQL = """
    SELECT
        country_code,
        COALESCE(MIN(country_name), MIN(country_code)) AS country_name,
        MIN(continent) AS continent,
        COUNT(*)::bigint AS hotspot_count,
        ST_YMin(ST_Extent(geom))::float8 AS min_latitude,
        ST_XMin(ST_Extent(geom))::float8 AS min_longitude,
        ST_YMax(ST_Extent(geom))::float8 AS max_latitude,
        ST_XMax(ST_Extent(geom))::float8 AS max_longitude,
        ST_Y(ST_Centroid(ST_Collect(geom)))::float8 AS centroid_latitude,
        ST_X(ST_Centroid(ST_Collect(geom)))::float8 AS centroid_longitude
    FROM public.fire_hotspots
    WHERE country_code IS NOT NULL
    GROUP BY country_code
    ORDER BY COUNT(*) DESC, country_code
"""


class RegionRepository:
    """Read-only country aggregates derived from fire hotspot locations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def list_regions(self) -> list[dict[str, Any]]:
        rows = await self.database.fetch(REGION_AGGREGATE_SQL)
        return [dict(row) for row in rows]

    async def exists(self, country_code: str) -> bool:
        """Validate a three-letter country code against available records."""
        value = await self.database.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM public.fire_hotspots
                WHERE country_code = $1
                LIMIT 1
            )
            """,
            country_code,
        )
        return bool(value)
