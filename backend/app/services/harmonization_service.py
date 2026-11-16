"""Business logic for harmonized activity and its time-series analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from app.core.config import Settings
from app.core.exceptions import DateRangeError, RegionNotFoundError
from app.repositories.harmonization_repository import HarmonizationRepository
from app.repositories.region_repository import RegionRepository
from app.repositories.validation_repository import ValidationRepository
from app.schemas.activity import (
    ActivityCalendarDay,
    ActivityCalendarMeta,
    ActivityCalendarResponse,
    ActivityFilters,
    ActivityListResponse,
    ActivityPagination,
    ActivityRecord,
    HarmonizedAnomalyMeta,
    HarmonizedAnomalyRecord,
    HarmonizedAnomalyResponse,
    HarmonizedComparisonMeta,
    HarmonizedComparisonRecord,
    HarmonizedComparisonResponse,
    HarmonizedMonthlyPoint,
    HarmonizedSeasonalMeta,
    HarmonizedSeasonalPoint,
    HarmonizedSeasonalResponse,
)
from app.schemas.validation import (
    ValidationFilters,
    ValidationListResponse,
    ValidationPagination,
    ValidationRecord,
)
from app.utils.seasons import month_name, season_code_for_month, season_year_for
from app.utils.statistics import (
    anomaly_severity,
    modified_z_score,
    percentage_difference,
)

ACTIVITY_AGGREGATION_METHOD = (
    "Daily harmonized activity and MODIS/VIIRS counts are summed across matching "
    "grid records within each method version. Corrected totals remain null if "
    "any matching grid record lacks an estimate. Uncertainty is returned only for "
    "a single grid record; no multi-grid uncertainty aggregation is assumed."
)
SEASON_METHOD = (
    "DJF (Dec-Feb), MAM (Mar-May), JJA (Jun-Aug), and SON (Sep-Nov); December "
    "is assigned to the season ending in the following year. Harmonized rows "
    "do not contain a latitude, so seasons are returned as hemisphere-neutral "
    "codes without northern/southern labels."
)
BASELINE_METHOD = (
    "For each calendar month and method version, whole-month totals from each "
    "prior year are baseline observations. Mean and median are calculated over "
    "distinct prior years. At least the configured number of prior years is "
    "required before historical statistics are returned."
)
ANOMALY_METHOD = (
    "Observed monthly totals are compared with totals for the same calendar "
    "month and method version in prior years. The baseline location is the "
    "median and robust scale is the median absolute deviation (MAD)."
)
SCORE_FORMULA = "modified_z = 0.6745 * (observed - median) / MAD"


async def _ensure_region_pk(
    region_pk: int | None, repository: RegionRepository
) -> None:
    if region_pk is not None and not await repository.exists_by_id(region_pk):
        raise RegionNotFoundError(f"Region primary key '{region_pk}' was not found.")


async def _resolve_activity_period(
    repository: HarmonizationRepository,
    filters: ActivityFilters,
    *,
    single_year: bool = False,
) -> tuple[ActivityFilters, date | None, date | None]:
    start = filters.start_date
    end = filters.end_date
    if start is None and end is None:
        _, latest = await repository.date_bounds(filters, include_dates=False)
        if latest is None:
            return filters, None, None
        start = date(latest.year, 1, 1)
        end = date(latest.year, 12, 31)
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


class HarmonizationService:
    def __init__(
        self,
        repository: HarmonizationRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def list_activity(
        self, filters: ActivityFilters, *, limit: int, offset: int
    ) -> ActivityListResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        rows, total = await self.repository.list(filters, limit=limit, offset=offset)
        return ActivityListResponse(
            status="ok",
            data=[ActivityRecord(**row) for row in rows],
            pagination=ActivityPagination(limit=limit, offset=offset, total=total),
        )

    async def calendar(self, filters: ActivityFilters) -> ActivityCalendarResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        start = filters.start_date
        end = filters.end_date
        if start is None and end is None:
            _, latest = await self.repository.date_bounds(filters, include_dates=False)
            if latest is None:
                return self._empty_calendar(filters)
            end = latest
            start = end - timedelta(days=29)
        elif start is None or end is None:
            raise DateRangeError("start_date and end_date must be provided together.")
        if start > end:
            raise DateRangeError(
                "start_date must be earlier than or equal to end_date."
            )

        total_days = (end - start).days + 1
        if total_days > self.settings.max_calendar_days:
            raise DateRangeError(
                f"Calendar ranges are limited to {self.settings.max_calendar_days} days."
            )

        rows = await self.repository.daily_calendar(filters, start=start, end=end)
        if not rows:
            return self._empty_calendar(filters, start=start, end=end)
        data = [ActivityCalendarDay(**row) for row in rows]
        values = [row.harmonized_activity for row in data]
        versions = {row.method_version for row in data}
        single_version = len(versions) == 1
        total_activity = None
        total_modis = None
        total_viirs = None
        if single_version:
            total_activity = (
                sum(value for value in values if value is not None)
                if any(value is not None for value in values)
                and all(
                    row.harmonized_activity is not None or row.grid_records == 0
                    for row in data
                )
                else None
            )
            total_modis = sum(row.modis_count for row in data)
            total_viirs = sum(row.viirs_count for row in data)
        return ActivityCalendarResponse(
            status="ok",
            data=data,
            meta=ActivityCalendarMeta(
                start_date=start,
                end_date=end,
                total_days=total_days,
                total_harmonized_activity=total_activity,
                total_modis_count=total_modis,
                total_viirs_count=total_viirs,
                region_pk=filters.region_pk,
                spatial_grid_id=filters.spatial_grid_id,
                method_versions=sorted({row.method_version for row in data}),
                aggregation_method=ACTIVITY_AGGREGATION_METHOD,
            ),
        )

    def _empty_calendar(
        self,
        filters: ActivityFilters,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> ActivityCalendarResponse:
        return ActivityCalendarResponse(
            status="no_data",
            data=[],
            meta=ActivityCalendarMeta(
                start_date=start or filters.start_date,
                end_date=end or filters.end_date,
                total_days=0,
                total_harmonized_activity=None,
                total_modis_count=0,
                total_viirs_count=0,
                region_pk=filters.region_pk,
                spatial_grid_id=filters.spatial_grid_id,
                method_versions=[],
                aggregation_method=ACTIVITY_AGGREGATION_METHOD,
            ),
        )

    async def seasonal(self, filters: ActivityFilters) -> HarmonizedSeasonalResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        scoped, start, end = await _resolve_activity_period(self.repository, filters)
        rows = await self.repository.monthly_activity(scoped)
        monthly = [
            HarmonizedMonthlyPoint(
                year=int(row["year"]),
                month=int(row["month"]),
                month_name=month_name(int(row["month"])),
                method_version=row["method_version"],
                harmonized_activity=float(row["harmonized_activity"]),
            )
            for row in rows
        ]
        totals: dict[tuple[int, str, str], float] = defaultdict(float)
        for point in monthly:
            season = season_code_for_month(point.month)
            season_year = season_year_for(point.year, point.month)
            totals[(season_year, season, point.method_version)] += (
                point.harmonized_activity
            )
        seasonal = [
            HarmonizedSeasonalPoint(
                season_year=year,
                season=season,
                method_version=version,
                harmonized_activity=value,
            )
            for (year, season, version), value in totals.items()
        ]
        seasonal.sort(
            key=lambda point: (
                point.season_year,
                ("DJF", "MAM", "JJA", "SON").index(point.season),
                point.method_version,
            )
        )
        versions = {point.method_version for point in monthly}
        total = (
            sum(point.harmonized_activity for point in monthly)
            if len(versions) == 1
            else None
        )
        return HarmonizedSeasonalResponse(
            status="ok" if monthly else "no_data",
            data=monthly,
            seasonal=seasonal,
            meta=HarmonizedSeasonalMeta(
                start_date=start,
                end_date=end,
                total_harmonized_activity=total,
                region_pk=filters.region_pk,
                spatial_grid_id=filters.spatial_grid_id,
                method_version=filters.method_version,
                aggregation_method=ACTIVITY_AGGREGATION_METHOD,
                season_method=SEASON_METHOD,
            ),
        )

    async def comparison(
        self, filters: ActivityFilters
    ) -> HarmonizedComparisonResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        scoped, start, end = await _resolve_activity_period(
            self.repository, filters, single_year=True
        )
        required = self.settings.historical_min_years
        base_meta = {
            "observed_start_date": start,
            "observed_end_date": end,
            "required_prior_years": required,
            "available_prior_years": 0,
            "region_pk": filters.region_pk,
            "spatial_grid_id": filters.spatial_grid_id,
            "method_version": filters.method_version,
            "baseline_method": BASELINE_METHOD,
        }
        if start is None or end is None:
            return HarmonizedComparisonResponse(
                status="no_data",
                message="No data is available for the selected filters.",
                meta=HarmonizedComparisonMeta(**base_meta),
                data=[],
            )

        observed = await self.repository.observed_monthly_activity(scoped)
        if not observed:
            return HarmonizedComparisonResponse(
                status="no_data",
                message="No harmonized estimates match the selected period.",
                meta=HarmonizedComparisonMeta(**base_meta),
                data=[],
            )
        baselines = await self.repository.historical_monthly_activity(
            scoped, before_year=start.year
        )
        baseline_map = {
            (int(row["month"]), row["method_version"]): row for row in baselines
        }
        available = max(
            (int(row["baseline_years"]) for row in baselines),
            default=0,
        )
        data: list[HarmonizedComparisonRecord] = []
        for row in sorted(
            observed, key=lambda item: (item["method_version"], item["month"])
        ):
            month = int(row["month"])
            version = row["method_version"]
            baseline = baseline_map.get((month, version))
            years = int(baseline["baseline_years"]) if baseline else 0
            enough = years >= required
            mean = float(baseline["historical_mean"]) if enough else None
            median = float(baseline["historical_median"]) if enough else None
            observed_activity = float(row["observed_activity"])
            data.append(
                HarmonizedComparisonRecord(
                    period=month_name(month),
                    month=month,
                    method_version=version,
                    observed_activity=observed_activity,
                    historical_mean=round(mean, 2) if mean is not None else None,
                    historical_median=round(median, 2) if median is not None else None,
                    difference_percent=percentage_difference(observed_activity, mean),
                    baseline_years=years,
                    status="ok" if enough else "insufficient_history",
                )
            )
        overall_status = (
            "ok" if all(row.status == "ok" for row in data) else "insufficient_history"
        )
        message = (
            "Historical comparison completed."
            if overall_status == "ok"
            else f"At least {required} prior years are required; statistics are "
            "omitted for groups with insufficient history."
        )
        base_meta["available_prior_years"] = available
        return HarmonizedComparisonResponse(
            status=overall_status,
            message=message,
            meta=HarmonizedComparisonMeta(**base_meta),
            data=data,
        )

    async def anomalies(self, filters: ActivityFilters) -> HarmonizedAnomalyResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        scoped, start, end = await _resolve_activity_period(
            self.repository, filters, single_year=True
        )
        required = self.settings.historical_min_years
        base_meta = {
            "observed_start_date": start,
            "observed_end_date": end,
            "required_prior_years": required,
            "available_prior_years": 0,
            "region_pk": filters.region_pk,
            "spatial_grid_id": filters.spatial_grid_id,
            "method_version": filters.method_version,
            "method": ANOMALY_METHOD,
            "score_formula": SCORE_FORMULA,
            "moderate_threshold": self.settings.anomaly_moderate_threshold,
            "high_threshold": self.settings.anomaly_high_threshold,
        }
        if start is None or end is None:
            return HarmonizedAnomalyResponse(
                status="no_data",
                message="No data is available for the selected filters.",
                meta=HarmonizedAnomalyMeta(**base_meta),
                data=[],
            )

        observed = await self.repository.observed_monthly_activity(scoped)
        if not observed:
            return HarmonizedAnomalyResponse(
                status="no_data",
                message="No harmonized estimates match the selected period.",
                meta=HarmonizedAnomalyMeta(**base_meta),
                data=[],
            )
        baseline_rows = await self.repository.historical_monthly_mad(
            scoped, before_year=start.year
        )
        baselines = {
            (int(row["month"]), row["method_version"]): row for row in baseline_rows
        }
        available = max(
            (int(row["baseline_years"]) for row in baseline_rows),
            default=0,
        )
        data: list[HarmonizedAnomalyRecord] = []
        zero_variance = 0
        for row in sorted(
            observed, key=lambda item: (item["method_version"], item["month"])
        ):
            month = int(row["month"])
            version = row["method_version"]
            observed_activity = float(row["observed_activity"])
            baseline = baselines.get((month, version))
            years = int(baseline["baseline_years"]) if baseline else 0
            mean = median = mad = score = None
            severity = direction = None
            is_anomaly = False
            row_status = "insufficient_history"
            if baseline is not None and years >= required:
                mean = float(baseline["historical_mean"])
                median = float(baseline["historical_median"])
                mad = float(baseline["mad"])
                if mad <= 0:
                    if observed_activity == median:
                        score = 0.0
                        severity = "normal"
                        direction = "normal"
                        row_status = "ok"
                    else:
                        direction = "above" if observed_activity > median else "below"
                        row_status = "insufficient_variance"
                        zero_variance += 1
                else:
                    score = modified_z_score(observed_activity, median, mad)
                    severity = anomaly_severity(
                        score,
                        moderate_threshold=self.settings.anomaly_moderate_threshold,
                        high_threshold=self.settings.anomaly_high_threshold,
                    )
                    direction = (
                        "normal"
                        if score == 0
                        else "above"
                        if score is not None and score > 0
                        else "below"
                    )
                    is_anomaly = severity in ("moderate", "high")
                    row_status = "ok"
            data.append(
                HarmonizedAnomalyRecord(
                    date=date(start.year, month, 1),
                    period=f"{start.year}-{month:02d}",
                    month=month,
                    method_version=version,
                    observed_activity=observed_activity,
                    historical_mean=round(mean, 2) if mean is not None else None,
                    historical_median=round(median, 2) if median is not None else None,
                    mad=round(mad, 2) if mad is not None else None,
                    anomaly_score=round(score, 2) if score is not None else None,
                    severity=severity,
                    direction=direction,
                    is_anomaly=is_anomaly,
                    baseline_years=years,
                    status=row_status,
                )
            )
        status = (
            "insufficient_history"
            if any(row.status == "insufficient_history" for row in data)
            else "ok"
        )
        message = (
            "Robust monthly anomaly detection completed."
            if status == "ok"
            else f"At least {required} prior years are required for each monthly "
            "method-version baseline."
        )
        if zero_variance:
            message += (
                f" {zero_variance} month/version group(s) had zero MAD and are "
                "reported as insufficient_variance when activity differs from "
                "the median."
            )
        base_meta["available_prior_years"] = available
        return HarmonizedAnomalyResponse(
            status=status,
            message=message,
            meta=HarmonizedAnomalyMeta(**base_meta),
            data=data,
        )


class ValidationService:
    def __init__(
        self,
        repository: ValidationRepository,
        region_repository: RegionRepository,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository

    async def list_reports(
        self, filters: ValidationFilters, *, limit: int, offset: int
    ) -> ValidationListResponse:
        await _ensure_region_pk(filters.region_pk, self.region_repository)
        rows, total = await self.repository.list(filters, limit=limit, offset=offset)
        return ValidationListResponse(
            status="ok",
            data=[ValidationRecord(**row) for row in rows],
            pagination=ValidationPagination(
                limit=limit,
                offset=offset,
                total=total,
            ),
        )
