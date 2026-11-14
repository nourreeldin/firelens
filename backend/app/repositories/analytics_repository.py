"""Parameterized raw-SQL analytics for calendar, seasons, and baselines."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from app.db.database import Database
from app.repositories.filters import build_fire_filters
from app.schemas.common import FireFilters


def _without_dates(filters: FireFilters) -> FireFilters:
    """Remove observed-period bounds so historical queries can reach prior years."""
    return filters.model_copy(update={"start_date": None, "end_date": None})


class AnalyticsRepository:
    """Read-only aggregate queries over ``public.fire_hotspots``."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def date_bounds(
        self, filters: FireFilters
    ) -> tuple[date | None, date | None]:
        builder = build_fire_filters(filters)
        row = await self.database.fetchrow(
            """
            SELECT MIN(acq_date) AS first_date, MAX(acq_date) AS last_date
            FROM public.fire_hotspots
            """
            + builder.where_sql,
            *builder.params,
        )
        if row is None:
            return None, None
        return row["first_date"], row["last_date"]

    async def latest_year(self, filters: FireFilters) -> int | None:
        builder = build_fire_filters(_without_dates(filters))
        value = await self.database.fetchval(
            """
            SELECT MAX(EXTRACT(YEAR FROM acq_date))::int
            FROM public.fire_hotspots
            """
            + builder.where_sql,
            *builder.params,
        )
        return int(value) if value is not None else None

    async def daily_counts(
        self,
        filters: FireFilters,
        *,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        """Return zero-filled daily counts using a database-generated series."""
        scoped = filters.model_copy(update={"start_date": start, "end_date": end})
        builder = build_fire_filters(scoped, param_offset=2)
        rows = await self.database.fetch(
            f"""
            WITH days AS (
                SELECT generate_series(
                    $1::date,
                    $2::date,
                    interval '1 day'
                )::date AS day
            ),
            counts AS (
                SELECT acq_date, COUNT(*)::bigint AS fire_count
                FROM public.fire_hotspots
                {builder.where_sql}
                GROUP BY acq_date
            )
            SELECT
                days.day,
                COALESCE(counts.fire_count, 0)::bigint AS fire_count
            FROM days
            LEFT JOIN counts ON counts.acq_date = days.day
            ORDER BY days.day
            """,
            start,
            end,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def available_prior_years(
        self,
        filters: FireFilters,
        *,
        observed_start_year: int,
        group_by: Literal["month", "season"],
    ) -> int:
        """Count distinct prior years represented before the observed period."""
        builder = build_fire_filters(_without_dates(filters))

        if group_by == "month":
            builder.add("EXTRACT(YEAR FROM acq_date)::int < {}", observed_start_year)
            query = """
                SELECT COUNT(DISTINCT EXTRACT(YEAR FROM acq_date)::int)
                FROM public.fire_hotspots
            """
        else:
            builder.add(
                """
                (CASE
                    WHEN EXTRACT(MONTH FROM acq_date)::int = 12
                    THEN EXTRACT(YEAR FROM acq_date)::int + 1
                    ELSE EXTRACT(YEAR FROM acq_date)::int
                END) < {}
                """,
                observed_start_year,
            )
            query = """
                SELECT COUNT(DISTINCT season_year)
                FROM (
                    SELECT (CASE
                        WHEN EXTRACT(MONTH FROM acq_date)::int = 12
                        THEN EXTRACT(YEAR FROM acq_date)::int + 1
                        ELSE EXTRACT(YEAR FROM acq_date)::int
                    END) AS season_year
                    FROM public.fire_hotspots
            """
            query += builder.where_sql
            query += ") AS seasons"
            value = await self.database.fetchval(query, *builder.params)
            return int(value or 0)

        value = await self.database.fetchval(query + builder.where_sql, *builder.params)
        return int(value or 0)

    async def monthly_counts(self, filters: FireFilters) -> list[dict[str, Any]]:
        """Return monthly counts split by hemisphere for seasonal analytics."""
        builder = build_fire_filters(filters)
        rows = await self.database.fetch(
            """
            SELECT
                EXTRACT(YEAR FROM acq_date)::int AS year,
                EXTRACT(MONTH FROM acq_date)::int AS month,
                (CASE
                    WHEN latitude < 0 THEN 'southern'
                    ELSE 'northern'
                END) AS hemisphere,
                COUNT(*)::bigint AS fire_count
            FROM public.fire_hotspots
            """
            + builder.where_sql
            + """
            GROUP BY 1, 2, 3
            ORDER BY 1, 2, 3
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]

    async def observed_comparison(
        self,
        filters: FireFilters,
        *,
        group_by: Literal["month", "season"],
    ) -> list[dict[str, Any]]:
        """Return counts for the selected period, grouped by month or season."""
        builder = build_fire_filters(filters)
        if group_by == "month":
            rows = await self.database.fetch(
                """
                SELECT
                    EXTRACT(MONTH FROM acq_date)::int AS month,
                    COUNT(*)::bigint AS observed_count,
                    COUNT(DISTINCT EXTRACT(YEAR FROM acq_date)::int)::int
                        AS observed_years
                FROM public.fire_hotspots
                """
                + builder.where_sql
                + " GROUP BY 1 ORDER BY 1",
                *builder.params,
            )
        else:
            rows = await self.database.fetch(
                """
                SELECT
                    season,
                    hemisphere,
                    COUNT(*)::bigint AS observed_count,
                    COUNT(DISTINCT season_year)::int AS observed_years
                FROM (
                    SELECT
                        (CASE
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (12, 1, 2)
                                THEN 'DJF'
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (3, 4, 5)
                                THEN 'MAM'
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (6, 7, 8)
                                THEN 'JJA'
                            ELSE 'SON'
                        END) AS season,
                        (CASE
                            WHEN latitude < 0 THEN 'southern'
                            ELSE 'northern'
                        END) AS hemisphere,
                        (CASE
                            WHEN EXTRACT(MONTH FROM acq_date)::int = 12
                            THEN EXTRACT(YEAR FROM acq_date)::int + 1
                            ELSE EXTRACT(YEAR FROM acq_date)::int
                        END) AS season_year
                    FROM public.fire_hotspots
                """
                + builder.where_sql
                + """
                ) AS grouped
                GROUP BY season, hemisphere
                ORDER BY season, hemisphere
                """,
                *builder.params,
            )
        return [dict(row) for row in rows]

    async def baseline_comparison(
        self,
        filters: FireFilters,
        *,
        observed_start_year: int,
        group_by: Literal["month", "season"],
    ) -> list[dict[str, Any]]:
        """Compute prior-year annual totals and their mean/median by grouping."""
        builder = build_fire_filters(_without_dates(filters))

        if group_by == "month":
            builder.add("EXTRACT(YEAR FROM acq_date)::int < {}", observed_start_year)
            rows = await self.database.fetch(
                """
                WITH yearly AS (
                    SELECT
                        EXTRACT(MONTH FROM acq_date)::int AS month,
                        EXTRACT(YEAR FROM acq_date)::int AS year,
                        COUNT(*)::bigint AS year_count
                    FROM public.fire_hotspots
                """
                + builder.where_sql
                + """
                    GROUP BY 1, 2
                )
                SELECT
                    month,
                    COUNT(*)::int AS baseline_years,
                    AVG(year_count)::float8 AS historical_mean,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY year_count
                    )::float8 AS historical_median,
                    MIN(year)::int AS first_year,
                    MAX(year)::int AS last_year
                FROM yearly
                GROUP BY month
                ORDER BY month
                """,
                *builder.params,
            )
        else:
            builder.add(
                """
                (CASE
                    WHEN EXTRACT(MONTH FROM acq_date)::int = 12
                    THEN EXTRACT(YEAR FROM acq_date)::int + 1
                    ELSE EXTRACT(YEAR FROM acq_date)::int
                END) < {}
                """,
                observed_start_year,
            )
            rows = await self.database.fetch(
                """
                WITH base AS (
                    SELECT
                        (CASE
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (12, 1, 2)
                                THEN 'DJF'
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (3, 4, 5)
                                THEN 'MAM'
                            WHEN EXTRACT(MONTH FROM acq_date)::int IN (6, 7, 8)
                                THEN 'JJA'
                            ELSE 'SON'
                        END) AS season,
                        (CASE
                            WHEN latitude < 0 THEN 'southern'
                            ELSE 'northern'
                        END) AS hemisphere,
                        (CASE
                            WHEN EXTRACT(MONTH FROM acq_date)::int = 12
                            THEN EXTRACT(YEAR FROM acq_date)::int + 1
                            ELSE EXTRACT(YEAR FROM acq_date)::int
                        END) AS season_year
                    FROM public.fire_hotspots
                """
                + builder.where_sql
                + """
                ),
                yearly AS (
                    SELECT
                        season,
                        hemisphere,
                        season_year,
                        COUNT(*)::bigint AS year_count
                    FROM base
                    GROUP BY 1, 2, 3
                )
                SELECT
                    season,
                    hemisphere,
                    COUNT(*)::int AS baseline_years,
                    AVG(year_count)::float8 AS historical_mean,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY year_count
                    )::float8 AS historical_median,
                    MIN(season_year)::int AS first_year,
                    MAX(season_year)::int AS last_year
                FROM yearly
                GROUP BY season, hemisphere
                ORDER BY season, hemisphere
                """,
                *builder.params,
            )
        return [dict(row) for row in rows]

    async def monthly_baseline(
        self,
        filters: FireFilters,
        *,
        observed_start_year: int,
    ) -> list[dict[str, Any]]:
        """Compute monthly median, MAD, and mean from prior-year monthly totals."""
        builder = build_fire_filters(_without_dates(filters))
        builder.add("EXTRACT(YEAR FROM acq_date)::int < {}", observed_start_year)
        rows = await self.database.fetch(
            """
            WITH yearly AS (
                SELECT
                    EXTRACT(MONTH FROM acq_date)::int AS month,
                    EXTRACT(YEAR FROM acq_date)::int AS year,
                    COUNT(*)::bigint AS year_count
                FROM public.fire_hotspots
            """
            + builder.where_sql
            + """
                GROUP BY 1, 2
            ),
            medians AS (
                SELECT
                    month,
                    COUNT(*)::int AS baseline_years,
                    AVG(year_count)::float8 AS historical_mean,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY year_count
                    )::float8 AS historical_median,
                    MIN(year)::int AS first_year,
                    MAX(year)::int AS last_year
                FROM yearly
                GROUP BY month
            ),
            deviations AS (
                SELECT
                    yearly.month,
                    ABS(yearly.year_count - medians.historical_median)
                        AS deviation
                FROM yearly
                JOIN medians ON medians.month = yearly.month
            ),
            mad_values AS (
                SELECT
                    month,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (
                        ORDER BY deviation
                    )::float8 AS mad
                FROM deviations
                GROUP BY month
            )
            SELECT
                medians.month,
                medians.baseline_years,
                medians.historical_mean,
                medians.historical_median,
                mad_values.mad,
                medians.first_year,
                medians.last_year
            FROM medians
            JOIN mad_values ON mad_values.month = medians.month
            ORDER BY medians.month
            """,
            *builder.params,
        )
        return [dict(row) for row in rows]
