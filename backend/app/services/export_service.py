"""Streaming CSV export for filtered fire detections."""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import AsyncIterator
from datetime import date, datetime
from enum import Enum

from app.core.config import Settings
from app.repositories.fire_repository import FireRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.common import FireFilters
from app.services.common import ensure_region_exists
from app.utils.csv import safe_csv_value
from app.utils.fire_rows import normalize_fire_row

logger = logging.getLogger(__name__)

EXPORT_COLUMNS = (
    "id",
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "acq_datetime_utc",
    "sensor",
    "confidence",
    "confidence_raw",
    "satellite",
    "version",
    "daynight",
    "brightness",
    "brightness_thermal",
    "scan",
    "track",
    "frp",
    "country_code",
    "country_name",
    "continent",
    "spatial_grid_id",
    "source_detection_id",
    "coordinate_reference_system",
    "bright_t31",
    "bright_ti4",
    "bright_ti5",
    "source_file",
    "instrument",
    "fire_type",
    "hour",
    "minute",
    "year",
    "month",
    "day",
    "day_of_year",
    "grid_lat",
    "grid_lon",
    "created_at",
)


def _csv_value(value: object) -> object:
    """Serialize dates and timestamps consistently before formula sanitization."""
    if value is None:
        return ""
    if isinstance(value, Enum):
        return _csv_value(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return safe_csv_value(value)


class ExportService:
    """Prepare a validated, database-streamed CSV response."""

    def __init__(
        self,
        repository: FireRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def prepare_export(self, filters: FireFilters) -> AsyncIterator[str]:
        """Validate the request now, then return a lazy streaming iterator."""
        await ensure_region_exists(filters, self.region_repository)
        return self._stream(filters)

    async def _stream(self, filters: FireFilters) -> AsyncIterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(EXPORT_COLUMNS)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        try:
            async for row in self.repository.stream(
                filters, batch_size=self.settings.export_batch_size
            ):
                payload = normalize_fire_row(row)
                writer.writerow(
                    [_csv_value(payload.get(column)) for column in EXPORT_COLUMNS]
                )
                if buffer.tell() >= self.settings.export_chunk_size:
                    yield buffer.getvalue()
                    buffer.seek(0)
                    buffer.truncate(0)
        except Exception:
            logger.exception("CSV export stream failed.")
            raise

        if buffer.tell():
            yield buffer.getvalue()
