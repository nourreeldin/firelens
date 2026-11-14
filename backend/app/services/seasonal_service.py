"""Hemisphere-aware monthly and seasonal analytics."""

from collections import defaultdict

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.analytics import (
    SeasonalMeta,
    SeasonalMonthlyPoint,
    SeasonalPoint,
    SeasonalResponse,
)
from app.schemas.common import FireFilters
from app.services.common import ensure_region_exists, resolve_analytics_period
from app.utils.seasons import (
    month_name,
    season_code_for_month,
    season_label,
    season_year_for,
)

SEASON_ORDER = {"DJF": 0, "MAM": 1, "JJA": 2, "SON": 3}
HEMISPHERE_ORDER = {"northern": 0, "southern": 1}

HEMISPHERE_METHOD = (
    "Each hotspot is classified by its own latitude: latitude < 0 is "
    "southern; latitude >= 0 is northern (the equator is grouped with the "
    "northern hemisphere)."
)
SEASON_METHOD = (
    "Meteorological seasons are DJF (Dec-Feb), MAM (Mar-May), JJA (Jun-Aug), "
    "and SON (Sep-Nov). December is assigned to the DJF season ending in the "
    "following year. Season names are hemisphere-aware: DJF is winter in the "
    "northern hemisphere and summer in the southern hemisphere."
)


class SeasonalService:
    """Aggregate monthly counts and derive hemisphere-aware seasons."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        region_repository: RegionRepository,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository

    async def get_seasonal(self, filters: FireFilters) -> SeasonalResponse:
        await ensure_region_exists(filters, self.region_repository)
        scoped, start, end = await resolve_analytics_period(self.repository, filters)

        rows = await self.repository.monthly_counts(scoped)
        monthly = [
            SeasonalMonthlyPoint(
                year=int(row["year"]),
                month=int(row["month"]),
                month_name=month_name(int(row["month"])),
                hemisphere=row["hemisphere"],
                fire_count=int(row["fire_count"]),
            )
            for row in rows
        ]
        monthly.sort(key=lambda item: (item.year, item.month, item.hemisphere))

        season_totals: dict[tuple[int, str, str], int] = defaultdict(int)
        for point in monthly:
            code = season_code_for_month(point.month)
            season_year = season_year_for(point.year, point.month)
            season_totals[(season_year, code, point.hemisphere)] += point.fire_count

        seasonal = [
            SeasonalPoint(
                season_year=season_year,
                season=code,
                season_name=season_label(code, hemisphere),
                hemisphere=hemisphere,
                fire_count=count,
            )
            for (season_year, code, hemisphere), count in season_totals.items()
        ]
        seasonal.sort(
            key=lambda item: (
                item.season_year,
                HEMISPHERE_ORDER[item.hemisphere],
                SEASON_ORDER[item.season],
            )
        )

        total_fires = sum(point.fire_count for point in monthly)
        return SeasonalResponse(
            status="ok" if monthly else "no_data",
            data=monthly,
            seasonal=seasonal,
            meta=SeasonalMeta(
                start_date=start,
                end_date=end,
                total_fires=total_fires,
                region_id=filters.region_id,
                sensor=filters.sensor.value if filters.sensor else None,
                hemisphere_method=HEMISPHERE_METHOD,
                season_method=SEASON_METHOD,
            ),
        )
