"""Business logic for the zero-filled detection calendar."""

from datetime import timedelta

from app.core.config import Settings
from app.core.exceptions import DateRangeError
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.calendar import CalendarDay, CalendarMeta, CalendarResponse
from app.schemas.common import FireFilters
from app.services.common import ensure_region_exists


class CalendarService:
    """Build a daily calendar from database-side aggregates."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def get_calendar(self, filters: FireFilters) -> CalendarResponse:
        await ensure_region_exists(filters, self.region_repository)

        start = filters.start_date
        end = filters.end_date
        if start is None and end is None:
            _, latest = await self.repository.date_bounds(filters)
            if latest is None:
                return self._empty_response(filters)
            end = latest
            start = end - timedelta(days=29)
        elif start is None or end is None:
            raise DateRangeError("start_date and end_date must be provided together.")

        if start > end:
            raise DateRangeError(
                "start_date must be earlier than or equal to end_date."
            )

        day_count = (end - start).days + 1
        if day_count > self.settings.max_calendar_days:
            raise DateRangeError(
                "Calendar ranges are limited to "
                f"{self.settings.max_calendar_days} days."
            )

        rows = await self.repository.daily_counts(filters, start=start, end=end)
        data = [
            CalendarDay(
                date=row["day"],
                fire_count=int(row["fire_count"]),
            )
            for row in rows
        ]
        total = sum(day.fire_count for day in data)

        return CalendarResponse(
            status="ok",
            data=data,
            meta=CalendarMeta(
                start_date=start,
                end_date=end,
                total_days=day_count,
                total_fires=total,
                region_id=filters.region_id,
                sensor=filters.sensor.value if filters.sensor else None,
            ),
        )

    def _empty_response(self, filters: FireFilters) -> CalendarResponse:
        return CalendarResponse(
            status="no_data",
            data=[],
            meta=CalendarMeta(
                start_date=filters.start_date,
                end_date=filters.end_date,
                total_days=0,
                total_fires=0,
                region_id=filters.region_id,
                sensor=filters.sensor.value if filters.sensor else None,
            ),
        )
