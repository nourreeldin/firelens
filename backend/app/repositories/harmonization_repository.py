"""Parameterized raw-SQL access to corrected harmonized activity."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from typing import Any

from app.db.database import Database
from app.repositories.filters import WhereBuilder
from app.schemas.activity import ActivityFilters


def _activity_where(
    filters: ActivityFilters,
    *,
    include_dates: bool = True,
    param_offset: int = 0,
) -> WhereBuilder:
    builder = WhereBuilder(param_offset=param_offset)
    if include_dates and filters.start_date is not None:
        builder.add("activity_date >= {}", filters.start_date)
    if include_dates and filters.end_date is not None:
        builder.add("activity_date <= {}", filters.end_date)
    if filters.region_pk is not None:
        builder.add("region_id = {}", filters.region_pk)
    if filters.spatial_grid_id is not None:
        builder.add("spatial_grid_id = {}", filters.spatial_grid_id)
    if filters.method_version is not None:
        builder.add("method_version = {}", filters.method_version)
    return builder


class HarmonizationRepository:
    """Read-only query methods for ``public.harmonized_activity``."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def date_bounds(
        self, filters: ActivityFilters, *, include_dates: bool = True
    ) -> tuple[date | None, date | None]:
        builder = _activity_where(filters, include_dates=include_dates)
        row = await self.database.fetchrow(
            """
            SELECT MIN(activity_date) AS first_date, MAX(activity_date) AS last_date
            FROM public.harmonized_activity
            """
            + builder.where_sql,
            *builder.params,
        )
        if row is None:
            return None, None
        return row["first_date"], row["last_date"]

    async def list(
        self,
        filters: ActivityFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        builder = _activity_where(filters)
        total = int(
            await self.database.fetchval(
                "SELECT COUNT(*) FROM public.harmonized_activity " + builder.where_sql,
                *builder.params,
            )
            or 0
        )
        limit_position = len(builder.params) + 1
        offset_position = len(builder.params) + 2
        rows = await self.database.fetch(
            f"""
            SELECT
                activity.id,
                activity.region_id,
                regions.country_code,
                activity.activity_date,
                activity.spatial_grid_id,
                activity.modis_count,
                activity.viirs_count,
                activity.harmonized_count,
                activity.correction_factor,
                activity.uncertainty,
                activity.method_version,
                activity.created_at
            FROM public.harmonized_activity AS activity
            LEFT JOIN public.regions AS regions ON regions.id = activity.region_id
            {builder.where_sql}
            ORDER BY activity.activity_date DESC, activity.id DESC
            LIMIT ${limit_position} OFFSET ${offset_position}
            """,
            *builder.params,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total

    async def daily_calendar(
        self,
        filters: ActivityFilters,
        *,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        scoped = filters.model_copy(update={"start_date": start, "end_date": end})
        builder = _activity_where(scoped, param_offset=2)
        rows = await self.database.fetch(
            f"""
            WITH days AS (
                SELECT generate_series($1::date, $2::date, interval '1 day')::date AS day
            ),
            matching AS (
                SELECT activity_date, method_version, modis_count, viirs_count,
                       harmonized_count, uncertainty
                FROM public.harmonized_activity
                {builder.where_sql}
            ),
            versions AS (
                SELECT DISTINCT method_version FROM matching
            ),
            daily AS (
                SELECT
                    activity_date,
                    method_version,
                    SUM(modis_count)::bigint AS modis_count,
                    SUM(viirs_count)::bigint AS viirs_count,
                    CASE WHEN COUNT(harmonized_count) = COUNT(*)
                         THEN SUM(harmonized_count)::float8 END AS harmonized_activity,
                    COUNT(*)::bigint AS grid_records,
                    CASE WHEN COUNT(*) = 1 THEN MAX(uncertainty)::float8 END
                        AS uncertainty
                FROM matching
                GROUP BY activity_date, method_version
            )
            SELECT
                days.day AS date,
                versions.method_version,
                COALESCE(daily.modis_count, 0)::bigint AS modis_count,
                COALESCE(daily.viirs_count, 0)::bigint AS viirs_count,
                daily.harmonized_activity,
                COALESCE(daily.grid_records, 0)::bigint AS grid_records,
                daily.uncertainty
            FROM days
            CROSS JOIN versions
            LEFT JOIN daily
                ON daily.activity_date = days.day
               AND daily.method_version = versions.method_version
            ORDER BY days.day, versions.method_version
            """,
            start,
            end,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def monthly_activity(self, filters: ActivityFilters) -> list[dict[str, Any]]:
        builder = _activity_where(filters)
        rows = await self.database.fetch(
            """
            SELECT
                EXTRACT(YEAR FROM activity_date)::int AS year,
                EXTRACT(MONTH FROM activity_date)::int AS month,
                method_version,
                SUM(harmonized_count)::float8 AS harmonized_activity
            FROM public.harmonized_activity
            """
            + builder.where_sql
            + """
            GROUP BY 1, 2, 3
            HAVING SUM(harmonized_count) IS NOT NULL
            ORDER BY 1, 2, 3
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def observed_monthly_activity(
        self, filters: ActivityFilters
    ) -> list[dict[str, Any]]:
        builder = _activity_where(filters)
        rows = await self.database.fetch(
            """
            SELECT
                EXTRACT(MONTH FROM activity_date)::int AS month,
                method_version,
                SUM(harmonized_count)::float8 AS observed_activity
            FROM public.harmonized_activity
            """
            + builder.where_sql
            + """
            GROUP BY 1, 2
            HAVING SUM(harmonized_count) IS NOT NULL
            ORDER BY 2, 1
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def historical_monthly_activity(
        self,
        filters: ActivityFilters,
        *,
        before_year: int,
    ) -> list[dict[str, Any]]:
        builder = _activity_where(filters, include_dates=False)
        builder.add("activity_date < {}", date(before_year, 1, 1))
        rows = await self.database.fetch(
            """
            WITH yearly AS (
                SELECT
                    EXTRACT(YEAR FROM activity_date)::int AS year,
                    EXTRACT(MONTH FROM activity_date)::int AS month,
                    method_version,
                    SUM(harmonized_count)::float8 AS activity
                FROM public.harmonized_activity
            """
            + builder.where_sql
            + """
                GROUP BY 1, 2, 3
                HAVING SUM(harmonized_count) IS NOT NULL
            )
            SELECT
                month,
                method_version,
                COUNT(*)::int AS baseline_years,
                AVG(activity)::float8 AS historical_mean,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY activity)::float8
                    AS historical_median
            FROM yearly
            GROUP BY month, method_version
            ORDER BY method_version, month
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def historical_monthly_mad(
        self,
        filters: ActivityFilters,
        *,
        before_year: int,
    ) -> list[dict[str, Any]]:
        builder = _activity_where(filters, include_dates=False)
        builder.add("activity_date < {}", date(before_year, 1, 1))
        rows = await self.database.fetch(
            """
            WITH yearly AS (
                SELECT
                    EXTRACT(YEAR FROM activity_date)::int AS year,
                    EXTRACT(MONTH FROM activity_date)::int AS month,
                    method_version,
                    SUM(harmonized_count)::float8 AS activity
                FROM public.harmonized_activity
            """
            + builder.where_sql
            + """
                GROUP BY 1, 2, 3
                HAVING SUM(harmonized_count) IS NOT NULL
            ),
            centers AS (
                SELECT
                    month,
                    method_version,
                    COUNT(*)::int AS baseline_years,
                    AVG(activity)::float8 AS historical_mean,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY activity)::float8
                        AS historical_median
                FROM yearly
                GROUP BY month, method_version
            )
            SELECT
                centers.month,
                centers.method_version,
                centers.baseline_years,
                centers.historical_mean,
                centers.historical_median,
                PERCENTILE_CONT(0.5) WITHIN GROUP (
                    ORDER BY ABS(yearly.activity - centers.historical_median)
                )::float8 AS mad
            FROM centers
            JOIN yearly USING (month, method_version)
            GROUP BY centers.month, centers.method_version,
                     centers.baseline_years, centers.historical_mean,
                     centers.historical_median
            ORDER BY centers.method_version, centers.month
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def stream(
        self,
        filters: ActivityFilters,
        *,
        batch_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        builder = _activity_where(filters)
        query = f"""
            SELECT
                activity.id,
                activity.region_id,
                regions.country_code,
                activity.activity_date,
                activity.spatial_grid_id,
                activity.modis_count,
                activity.viirs_count,
                activity.harmonized_count,
                activity.correction_factor,
                activity.uncertainty,
                activity.method_version,
                activity.created_at
            FROM public.harmonized_activity AS activity
            LEFT JOIN public.regions AS regions ON regions.id = activity.region_id
            {builder.where_sql}
            ORDER BY activity.activity_date DESC, activity.id DESC
        """
        async with (
            self.database.acquire() as connection,
            connection.transaction(),
        ):
            cursor = connection.cursor(query, *builder.params, prefetch=batch_size)
            async for row in cursor:
                yield dict(row)
