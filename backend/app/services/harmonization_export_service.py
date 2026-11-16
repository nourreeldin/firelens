"""Streaming CSV exports for harmonized activity and validation reports."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import AsyncIterator
from datetime import date, datetime
from enum import Enum

from app.core.config import Settings
from app.core.exceptions import RegionNotFoundError
from app.repositories.harmonization_repository import HarmonizationRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.validation_repository import ValidationRepository
from app.schemas.activity import ActivityFilters
from app.schemas.validation import ValidationFilters
from app.utils.csv import safe_csv_value

logger = logging.getLogger(__name__)

HARMONIZATION_EXPORT_COLUMNS = (
    "id",
    "region_id",
    "country_code",
    "activity_date",
    "spatial_grid_id",
    "modis_count",
    "viirs_count",
    "harmonized_count",
    "correction_factor",
    "uncertainty",
    "method_version",
    "created_at",
)
VALIDATION_EXPORT_COLUMNS = (
    "id",
    "region_id",
    "country_code",
    "method_version",
    "validation_period_start",
    "validation_period_end",
    "mae",
    "rmse",
    "bias",
    "sample_size",
    "notes",
    "created_at",
)


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return _csv_value(value.value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return safe_csv_value(value)


class HarmonizationExportService:
    def __init__(
        self,
        activity_repository: HarmonizationRepository,
        validation_repository: ValidationRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.activity_repository = activity_repository
        self.validation_repository = validation_repository
        self.region_repository = region_repository
        self.settings = settings

    async def prepare_activity_export(
        self, filters: ActivityFilters
    ) -> AsyncIterator[str]:
        await self._ensure_region(filters.region_pk)
        return self._stream(
            self.activity_repository.stream(
                filters, batch_size=self.settings.export_batch_size
            ),
            HARMONIZATION_EXPORT_COLUMNS,
            "harmonization",
        )

    async def prepare_validation_export(
        self, filters: ValidationFilters
    ) -> AsyncIterator[str]:
        await self._ensure_region(filters.region_pk)
        return self._stream(
            self.validation_repository.stream(
                filters, batch_size=self.settings.export_batch_size
            ),
            VALIDATION_EXPORT_COLUMNS,
            "validation",
        )

    async def _ensure_region(self, region_pk: int | None) -> None:
        if region_pk is not None and not await self.region_repository.exists_by_id(
            region_pk
        ):
            raise RegionNotFoundError(
                f"Region primary key '{region_pk}' was not found."
            )

    async def _stream(
        self,
        rows: AsyncIterator[dict],
        columns: tuple[str, ...],
        label: str,
    ) -> AsyncIterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(columns)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        try:
            async for row in rows:
                writer.writerow([_csv_value(row.get(column)) for column in columns])
                if buffer.tell() >= self.settings.export_chunk_size:
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)
        except Exception:
            logger.exception("%s CSV export stream failed.", label)
            raise
        if buffer.tell():
            yield buffer.getvalue()
