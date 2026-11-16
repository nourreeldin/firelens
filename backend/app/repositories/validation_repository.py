"""Parameterized raw-SQL access to validation reports."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.db.database import Database
from app.repositories.filters import WhereBuilder
from app.schemas.validation import ValidationFilters


def _validation_where(filters: ValidationFilters) -> WhereBuilder:
    builder = WhereBuilder()
    if filters.region_pk is not None:
        builder.add("region_id = {}", filters.region_pk)
    if filters.method_version is not None:
        builder.add("method_version = {}", filters.method_version)
    if filters.start_date is not None:
        builder.add(
            "(validation_period_end IS NULL OR validation_period_end >= {})",
            filters.start_date,
        )
    if filters.end_date is not None:
        builder.add(
            "(validation_period_start IS NULL OR validation_period_start <= {})",
            filters.end_date,
        )
    return builder


class ValidationRepository:
    """Read-only query methods for ``public.validation_reports``."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def list(
        self,
        filters: ValidationFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        builder = _validation_where(filters)
        total = int(
            await self.database.fetchval(
                "SELECT COUNT(*) FROM public.validation_reports " + builder.where_sql,
                *builder.params,
            )
            or 0
        )
        limit_position = len(builder.params) + 1
        offset_position = len(builder.params) + 2
        rows = await self.database.fetch(
            f"""
            SELECT
                reports.id,
                reports.region_id,
                regions.country_code,
                reports.method_version,
                reports.validation_period_start,
                reports.validation_period_end,
                reports.mae,
                reports.rmse,
                reports.bias,
                reports.sample_size,
                reports.notes,
                reports.created_at
            FROM public.validation_reports AS reports
            LEFT JOIN public.regions AS regions ON regions.id = reports.region_id
            {builder.where_sql}
            ORDER BY reports.created_at DESC, reports.id DESC
            LIMIT ${limit_position} OFFSET ${offset_position}
            """,
            *builder.params,
            limit,
            offset,
        )
        return [dict(row) for row in rows], total

    async def stream(
        self,
        filters: ValidationFilters,
        *,
        batch_size: int,
    ) -> AsyncIterator[dict[str, Any]]:
        builder = _validation_where(filters)
        query = f"""
            SELECT
                reports.id,
                reports.region_id,
                regions.country_code,
                reports.method_version,
                reports.validation_period_start,
                reports.validation_period_end,
                reports.mae,
                reports.rmse,
                reports.bias,
                reports.sample_size,
                reports.notes,
                reports.created_at
            FROM public.validation_reports AS reports
            LEFT JOIN public.regions AS regions ON regions.id = reports.region_id
            {builder.where_sql}
            ORDER BY reports.created_at DESC, reports.id DESC
        """
        async with (
            self.database.acquire() as connection,
            connection.transaction(),
        ):
            cursor = connection.cursor(query, *builder.params, prefetch=batch_size)
            async for row in cursor:
                yield dict(row)
