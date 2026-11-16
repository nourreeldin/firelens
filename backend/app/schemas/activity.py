"""Request and response models for corrected harmonized activity."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivityFilters(BaseModel):
    """Filters for records in ``public.harmonized_activity``.

    ``region_pk`` is the integer ``regions.id``. The existing raw-fire
    ``region_id`` country-code filter remains unchanged.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: date | None = None
    end_date: date | None = None
    region_pk: int | None = Field(default=None, gt=0)
    spatial_grid_id: str | None = Field(default=None, min_length=1, max_length=255)
    method_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Exact activity method. The imported dataset uses "
            "daily-grid-modis-equivalent-v1. Omit to include all versions."
        ),
    )

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be earlier than or equal to end_date")
        return self


class ActivityPagination(BaseModel):
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class ActivityRecord(BaseModel):
    id: int
    region_id: int | None = Field(
        description="Integer public.regions.id; null means no region assignment."
    )
    country_code: str | None = None
    activity_date: date
    spatial_grid_id: str | None = None
    modis_count: int = Field(ge=0)
    viirs_count: int = Field(ge=0)
    harmonized_count: float | None = Field(
        default=None,
        ge=0,
        description="Fractional hotspot detection index; null means no estimate.",
    )
    correction_factor: float | None = None
    uncertainty: float | None = Field(default=None, ge=0)
    method_version: str
    created_at: datetime


class ActivityListResponse(BaseModel):
    status: Literal["ok"]
    data: list[ActivityRecord]
    pagination: ActivityPagination


class ActivityCalendarDay(BaseModel):
    date: date
    method_version: str
    harmonized_activity: float | None
    modis_count: int = Field(ge=0)
    viirs_count: int = Field(ge=0)
    grid_records: int = Field(ge=0)
    uncertainty: float | None = Field(
        description=(
            "The stored uncertainty when a day/version matches one grid record; "
            "null for multi-grid aggregates until an uncertainty aggregation "
            "method is defined."
        )
    )


class ActivityCalendarMeta(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    total_days: int = Field(ge=0)
    total_harmonized_activity: float | None = None
    total_modis_count: int | None = Field(default=None, ge=0)
    total_viirs_count: int | None = Field(default=None, ge=0)
    region_pk: int | None = None
    spatial_grid_id: str | None = None
    method_versions: list[str] = Field(default_factory=list)
    aggregation_method: str


class ActivityCalendarResponse(BaseModel):
    status: Literal["ok", "no_data"]
    data: list[ActivityCalendarDay]
    meta: ActivityCalendarMeta


class HarmonizedMonthlyPoint(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    month_name: str
    method_version: str
    harmonized_activity: float


class HarmonizedSeasonalPoint(BaseModel):
    season_year: int
    season: Literal["DJF", "MAM", "JJA", "SON"]
    method_version: str
    harmonized_activity: float


class HarmonizedSeasonalMeta(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    total_harmonized_activity: float | None
    region_pk: int | None = None
    spatial_grid_id: str | None = None
    method_version: str | None = None
    aggregation_method: str
    season_method: str


class HarmonizedSeasonalResponse(BaseModel):
    status: Literal["ok", "no_data"]
    data: list[HarmonizedMonthlyPoint]
    seasonal: list[HarmonizedSeasonalPoint]
    meta: HarmonizedSeasonalMeta


class HarmonizedComparisonRecord(BaseModel):
    period: str
    month: int = Field(ge=1, le=12)
    method_version: str
    observed_activity: float
    historical_mean: float | None = None
    historical_median: float | None = None
    difference_percent: float | None = None
    baseline_years: int = Field(ge=0)
    status: Literal["ok", "insufficient_history"]


class HarmonizedComparisonMeta(BaseModel):
    observed_start_date: date | None = None
    observed_end_date: date | None = None
    required_prior_years: int = Field(ge=1)
    available_prior_years: int = Field(ge=0)
    region_pk: int | None = None
    spatial_grid_id: str | None = None
    method_version: str | None = None
    baseline_method: str


class HarmonizedComparisonResponse(BaseModel):
    status: Literal["ok", "insufficient_history", "no_data"]
    message: str
    meta: HarmonizedComparisonMeta
    data: list[HarmonizedComparisonRecord]


class HarmonizedAnomalyRecord(BaseModel):
    date: date
    period: str
    month: int = Field(ge=1, le=12)
    method_version: str
    observed_activity: float
    historical_mean: float | None = None
    historical_median: float | None = None
    mad: float | None = None
    anomaly_score: float | None = None
    severity: Literal["normal", "moderate", "high"] | None = None
    direction: Literal["above", "below", "normal"] | None = None
    is_anomaly: bool = False
    baseline_years: int = Field(ge=0)
    status: Literal["ok", "insufficient_history", "insufficient_variance"]


class HarmonizedAnomalyMeta(BaseModel):
    observed_start_date: date | None = None
    observed_end_date: date | None = None
    required_prior_years: int = Field(ge=1)
    available_prior_years: int = Field(ge=0)
    region_pk: int | None = None
    spatial_grid_id: str | None = None
    method_version: str | None = None
    method: str
    score_formula: str
    moderate_threshold: float = Field(gt=0)
    high_threshold: float = Field(gt=0)


class HarmonizedAnomalyResponse(BaseModel):
    status: Literal["ok", "insufficient_history", "no_data"]
    message: str
    meta: HarmonizedAnomalyMeta
    data: list[HarmonizedAnomalyRecord]
