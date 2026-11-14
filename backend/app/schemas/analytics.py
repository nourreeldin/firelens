"""Pydantic schemas for seasonal, comparison, and anomaly analytics."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class SeasonalMonthlyPoint(BaseModel):
    """Monthly detection count split by hemisphere."""

    year: int
    month: int = Field(ge=1, le=12)
    month_name: str
    hemisphere: Literal["northern", "southern"]
    fire_count: int = Field(ge=0)


class SeasonalPoint(BaseModel):
    """Aggregate detection count for one hemisphere-aware season."""

    season_year: int
    season: str
    season_name: str
    hemisphere: Literal["northern", "southern"]
    fire_count: int = Field(ge=0)


class SeasonalMeta(BaseModel):
    """Time period, filters, and methodology for seasonal analytics."""

    start_date: date | None = None
    end_date: date | None = None
    total_fires: int = Field(ge=0)
    region_id: str | None = None
    sensor: str | None = None
    hemisphere_method: str
    season_method: str


class SeasonalResponse(BaseModel):
    """Monthly and meteorological-season aggregates."""

    status: Literal["ok", "no_data"]
    data: list[SeasonalMonthlyPoint]
    seasonal: list[SeasonalPoint]
    meta: SeasonalMeta


class ComparisonMeta(BaseModel):
    """Period, grouping, and baseline availability for a comparison."""

    observed_start_date: date | None = None
    observed_end_date: date | None = None
    group_by: Literal["month", "season"]
    required_prior_years: int = Field(ge=1)
    available_prior_years: int = Field(ge=0)
    baseline_method: str
    region_id: str | None = None
    sensor: str | None = None


class ComparisonRecord(BaseModel):
    """Observed activity and historical baseline for one grouping."""

    period: str
    month: int | None = Field(default=None, ge=1, le=12)
    season: str | None = None
    season_name: str | None = None
    hemisphere: Literal["northern", "southern"] | None = None
    observed_count: int = Field(ge=0)
    observed_years: int = Field(ge=0)
    historical_mean: float | None = None
    historical_median: float | None = None
    difference_percent: float | None = None
    baseline_years: int = Field(ge=0)
    status: Literal["ok", "insufficient_history"]


class ComparisonResponse(BaseModel):
    """Selected-period activity compared with prior-year baselines."""

    status: Literal["ok", "insufficient_history", "no_data"]
    message: str
    meta: ComparisonMeta
    data: list[ComparisonRecord]


class AnomalyMeta(BaseModel):
    """Period, thresholds, and methodology for anomaly detection."""

    observed_start_date: date | None = None
    observed_end_date: date | None = None
    required_prior_years: int = Field(ge=1)
    available_prior_years: int = Field(ge=0)
    method: str
    score_formula: str
    moderate_threshold: float = Field(gt=0)
    high_threshold: float = Field(gt=0)
    region_id: str | None = None
    sensor: str | None = None


class AnomalyRecord(BaseModel):
    """Observed monthly activity relative to its historical monthly baseline."""

    date: date
    period: str
    month: int = Field(ge=1, le=12)
    observed_count: int = Field(ge=0)
    historical_mean: float | None = None
    historical_median: float | None = None
    mad: float | None = None
    anomaly_score: float | None = None
    severity: Literal["normal", "moderate", "high"] | None = None
    direction: Literal["above", "below", "normal"] | None = None
    is_anomaly: bool = False
    baseline_years: int = Field(ge=0)
    status: Literal["ok", "insufficient_history", "insufficient_variance"]


class AnomalyResponse(BaseModel):
    """Monthly anomaly results for the selected period."""

    status: Literal["ok", "insufficient_history", "no_data"]
    message: str
    meta: AnomalyMeta
    data: list[AnomalyRecord]
