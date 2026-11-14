"""Robust monthly anomaly detection using median and MAD."""

from datetime import date

from app.core.config import Settings
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.analytics import AnomalyMeta, AnomalyRecord, AnomalyResponse
from app.schemas.common import FireFilters
from app.services.common import ensure_region_exists, resolve_analytics_period
from app.utils.statistics import anomaly_severity, modified_z_score

METHOD = (
    "Monthly observed totals are compared with the distribution of the same "
    "calendar month's totals in prior years. The baseline location is the "
    "median and the robust scale is the median absolute deviation (MAD)."
)
SCORE_FORMULA = "modified_z = 0.6745 * (observed - median) / MAD"


class AnomalyService:
    """Detect unusually high or low monthly activity."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def detect(self, filters: FireFilters) -> AnomalyResponse:
        await ensure_region_exists(filters, self.region_repository)
        scoped, start, end = await resolve_analytics_period(
            self.repository, filters, single_year=True
        )
        required = self.settings.historical_min_years

        if start is None or end is None:
            return self._no_data_response(filters, required=required)

        available = await self.repository.available_prior_years(
            scoped,
            observed_start_year=start.year,
            group_by="month",
        )
        observed_rows = await self.repository.observed_comparison(
            scoped, group_by="month"
        )
        if not observed_rows:
            return AnomalyResponse(
                status="no_data",
                message="No detections match the selected period and filters.",
                meta=self._meta(scoped, start, end, required, available),
                data=[],
            )

        baseline_rows = await self.repository.monthly_baseline(
            scoped, observed_start_year=start.year
        )
        baselines = {int(row["month"]): row for row in baseline_rows}

        records: list[AnomalyRecord] = []
        zero_variance_count = 0
        for row in sorted(observed_rows, key=lambda item: int(item["month"])):
            month = int(row["month"])
            observed = int(row["observed_count"])
            baseline = baselines.get(month)
            baseline_years = int(baseline["baseline_years"]) if baseline else 0

            mean = None
            median = None
            mad = None
            score = None
            severity = None
            direction = None
            is_anomaly = False
            row_status: str = "insufficient_history"

            if baseline is not None and baseline_years >= required:
                mean = float(baseline["historical_mean"])
                median = float(baseline["historical_median"])
                mad = float(baseline["mad"])

                if mad <= 0:
                    if observed == median:
                        score = 0.0
                        severity = "normal"
                        direction = "normal"
                        row_status = "ok"
                    else:
                        direction = "above" if observed > median else "below"
                        row_status = "insufficient_variance"
                        zero_variance_count += 1
                else:
                    score = modified_z_score(observed, median, mad)
                    severity = anomaly_severity(
                        score,
                        moderate_threshold=self.settings.anomaly_moderate_threshold,
                        high_threshold=self.settings.anomaly_high_threshold,
                    )
                    if score == 0:
                        direction = "normal"
                    else:
                        direction = "above" if score > 0 else "below"
                    is_anomaly = severity in ("moderate", "high")
                    row_status = "ok"

            records.append(
                AnomalyRecord(
                    date=date(start.year, month, 1),
                    period=f"{start.year}-{month:02d}",
                    month=month,
                    observed_count=observed,
                    historical_mean=round(mean, 2) if mean is not None else None,
                    historical_median=(
                        round(median, 2) if median is not None else None
                    ),
                    mad=round(mad, 2) if mad is not None else None,
                    anomaly_score=(round(score, 2) if score is not None else None),
                    severity=severity,
                    direction=direction,
                    is_anomaly=is_anomaly,
                    baseline_years=baseline_years,
                    status=row_status,
                )
            )

        if available < required:
            status = "insufficient_history"
            message = (
                f"At least {required} prior years are required for anomaly "
                f"detection; {available} available. No anomaly scores were "
                "fabricated."
            )
        else:
            status = "ok"
            message = "Robust monthly anomaly detection completed."
            if zero_variance_count:
                message += (
                    f" {zero_variance_count} period(s) had zero MAD and are "
                    "reported as insufficient_variance when they differ from "
                    "the median."
                )

        return AnomalyResponse(
            status=status,
            message=message,
            meta=self._meta(scoped, start, end, required, available),
            data=records,
        )

    def _meta(
        self,
        filters: FireFilters,
        start: date | None,
        end: date | None,
        required: int,
        available: int,
    ) -> AnomalyMeta:
        return AnomalyMeta(
            observed_start_date=start,
            observed_end_date=end,
            required_prior_years=required,
            available_prior_years=available,
            method=METHOD,
            score_formula=SCORE_FORMULA,
            moderate_threshold=self.settings.anomaly_moderate_threshold,
            high_threshold=self.settings.anomaly_high_threshold,
            region_id=filters.region_id,
            sensor=filters.sensor.value if filters.sensor else None,
        )

    def _no_data_response(
        self, filters: FireFilters, *, required: int
    ) -> AnomalyResponse:
        return AnomalyResponse(
            status="no_data",
            message="No data is available for the selected filters.",
            meta=self._meta(
                filters,
                filters.start_date,
                filters.end_date,
                required,
                0,
            ),
            data=[],
        )
