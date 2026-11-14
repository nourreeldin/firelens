"""Historical comparison against prior-year monthly or seasonal totals."""

from typing import Literal

from app.core.config import Settings
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.analytics import (
    ComparisonMeta,
    ComparisonRecord,
    ComparisonResponse,
)
from app.schemas.common import FireFilters
from app.services.common import ensure_region_exists, resolve_analytics_period
from app.utils.seasons import month_name, season_label
from app.utils.statistics import percentage_difference

BASELINE_METHOD = (
    "For each month or hemisphere-season, total counts from each prior year "
    "ending before the observed start year are treated as one baseline "
    "observation. Historical mean and median are calculated across those "
    "distinct years. At least 3 prior years are required before statistics "
    "are returned."
)
SEASON_ORDER = {"DJF": 0, "MAM": 1, "JJA": 2, "SON": 3}
HEMISPHERE_ORDER = {"northern": 0, "southern": 1}


class ComparisonService:
    """Compare observed activity with prior-year baselines."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def compare(
        self,
        filters: FireFilters,
        *,
        group_by: Literal["month", "season"] = "month",
    ) -> ComparisonResponse:
        await ensure_region_exists(filters, self.region_repository)
        scoped, start, end = await resolve_analytics_period(
            self.repository, filters, single_year=True
        )
        required = self.settings.historical_min_years

        if start is None or end is None:
            return self._no_data_response(filters, group_by=group_by, required=required)

        available = await self.repository.available_prior_years(
            scoped,
            observed_start_year=start.year,
            group_by=group_by,
        )
        observed_rows = await self.repository.observed_comparison(
            scoped, group_by=group_by
        )
        if not observed_rows:
            return ComparisonResponse(
                status="no_data",
                message="No detections match the selected period and filters.",
                meta=self._meta(
                    scoped,
                    start,
                    end,
                    group_by=group_by,
                    required=required,
                    available=available,
                ),
                data=[],
            )

        baseline_rows = await self.repository.baseline_comparison(
            scoped,
            observed_start_year=start.year,
            group_by=group_by,
        )

        data = (
            self._monthly_records(observed_rows, baseline_rows, required)
            if group_by == "month"
            else self._seasonal_records(observed_rows, baseline_rows, required)
        )

        if available < required:
            status = "insufficient_history"
            message = (
                f"At least {required} prior years are required for historical "
                f"comparison; {available} available. Historical statistics are "
                "not reported for insufficient groups."
            )
        else:
            status = "ok"
            message = "Historical comparison completed."

        return ComparisonResponse(
            status=status,
            message=message,
            meta=self._meta(
                scoped,
                start,
                end,
                group_by=group_by,
                required=required,
                available=available,
            ),
            data=data,
        )

    def _model(self, row: dict, required: int) -> ComparisonRecord:
        observed = int(row["observed_count"])
        years = int(row["baseline_years"])
        enough = years >= required
        mean = float(row["historical_mean"]) if enough else None
        median = float(row["historical_median"]) if enough else None
        return ComparisonRecord(
            period="",
            observed_count=observed,
            observed_years=int(row["observed_years"]),
            historical_mean=round(mean, 2) if mean is not None else None,
            historical_median=round(median, 2) if median is not None else None,
            difference_percent=percentage_difference(observed, mean),
            baseline_years=years,
            status="ok" if enough else "insufficient_history",
        )

    def _monthly_records(
        self,
        observed_rows: list[dict],
        baseline_rows: list[dict],
        required: int,
    ) -> list[ComparisonRecord]:
        baselines = {int(row["month"]): row for row in baseline_rows}
        records: list[ComparisonRecord] = []
        for row in sorted(observed_rows, key=lambda item: int(item["month"])):
            month = int(row["month"])
            combined = dict(row)
            baseline = baselines.get(month)
            combined["baseline_years"] = (
                int(baseline["baseline_years"]) if baseline else 0
            )
            combined["historical_mean"] = (
                baseline["historical_mean"] if baseline else None
            )
            combined["historical_median"] = (
                baseline["historical_median"] if baseline else None
            )
            record = self._model(combined, required)
            record.period = month_name(month)
            record.month = month
            records.append(record)
        return records

    def _seasonal_records(
        self,
        observed_rows: list[dict],
        baseline_rows: list[dict],
        required: int,
    ) -> list[ComparisonRecord]:
        baselines = {(row["season"], row["hemisphere"]): row for row in baseline_rows}
        records: list[ComparisonRecord] = []
        for row in sorted(
            observed_rows,
            key=lambda item: (
                SEASON_ORDER[item["season"]],
                HEMISPHERE_ORDER[item["hemisphere"]],
            ),
        ):
            season = str(row["season"])
            hemisphere = str(row["hemisphere"])
            combined = dict(row)
            baseline = baselines.get((season, hemisphere))
            combined["baseline_years"] = (
                int(baseline["baseline_years"]) if baseline else 0
            )
            combined["historical_mean"] = (
                baseline["historical_mean"] if baseline else None
            )
            combined["historical_median"] = (
                baseline["historical_median"] if baseline else None
            )
            record = self._model(combined, required)
            record.period = season
            record.season = season
            record.season_name = season_label(season, hemisphere)
            record.hemisphere = hemisphere
            records.append(record)
        return records

    def _meta(
        self,
        filters: FireFilters,
        start,
        end,
        *,
        group_by: Literal["month", "season"],
        required: int,
        available: int,
    ) -> ComparisonMeta:
        return ComparisonMeta(
            observed_start_date=start,
            observed_end_date=end,
            group_by=group_by,
            required_prior_years=required,
            available_prior_years=available,
            baseline_method=BASELINE_METHOD,
            region_id=filters.region_id,
            sensor=filters.sensor.value if filters.sensor else None,
        )

    def _no_data_response(
        self,
        filters: FireFilters,
        *,
        group_by: Literal["month", "season"],
        required: int,
    ) -> ComparisonResponse:
        return ComparisonResponse(
            status="no_data",
            message="No data is available for the selected filters.",
            meta=ComparisonMeta(
                observed_start_date=filters.start_date,
                observed_end_date=filters.end_date,
                group_by=group_by,
                required_prior_years=required,
                available_prior_years=0,
                baseline_method=BASELINE_METHOD,
                region_id=filters.region_id,
                sensor=filters.sensor.value if filters.sensor else None,
            ),
            data=[],
        )
