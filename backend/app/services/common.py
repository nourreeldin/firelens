"""Shared service helpers for filter validation and date periods."""

from datetime import date

from app.core.exceptions import DateRangeError, RegionNotFoundError
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.common import FireFilters


async def ensure_region_exists(
    filters: FireFilters, repository: RegionRepository
) -> None:
    """Validate a supplied region code against available country records."""
    if filters.region_id is None:
        return
    if not await repository.exists(filters.region_id):
        raise RegionNotFoundError(f"Region '{filters.region_id}' was not found.")


async def resolve_analytics_period(
    repository: AnalyticsRepository,
    filters: FireFilters,
    *,
    single_year: bool = False,
) -> tuple[FireFilters, date | None, date | None]:
    """Resolve explicit dates or default to the latest available year.

    Passing only one bound is rejected. When both bounds are omitted, the
    latest year represented by the filtered dataset is used, avoiding a
    wall-clock year that may not exist in the historical dataset.
    """
    start = filters.start_date
    end = filters.end_date

    if start is None and end is None:
        latest_year = await repository.latest_year(filters)
        if latest_year is None:
            return filters, None, None
        start = date(latest_year, 1, 1)
        end = date(latest_year, 12, 31)
    elif start is None or end is None:
        raise DateRangeError("start_date and end_date must be provided together.")

    if start > end:
        raise DateRangeError("start_date must be earlier than or equal to end_date.")
    if single_year and start.year != end.year:
        raise DateRangeError(
            "Comparison and anomaly periods must be within a single calendar "
            "year. Narrow start_date and end_date."
        )

    scoped = filters.model_copy(update={"start_date": start, "end_date": end})
    return scoped, start, end
