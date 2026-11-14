"""Seasonal, historical comparison, and anomaly analytics endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_anomaly_service,
    get_comparison_service,
    get_seasonal_service,
)
from app.schemas.analytics import (
    AnomalyResponse,
    ComparisonResponse,
    SeasonalResponse,
)
from app.schemas.common import FireFilters
from app.services.anomaly_service import AnomalyService
from app.services.comparison_service import ComparisonService
from app.services.seasonal_service import SeasonalService

router = APIRouter(prefix="/analytics", tags=["analytics"])

_ANALYTICS_RESPONSES = {
    404: {"description": "The requested region code was not found."},
    422: {"description": "Invalid date range or grouping."},
}


@router.get(
    "/seasonal",
    response_model=SeasonalResponse,
    summary="Hemisphere-aware seasonal aggregates",
    description=(
        "Return monthly counts split by hemisphere and derived meteorological "
        "seasons. Each hotspot is classified by its latitude. DJF/MAM/JJA/SON "
        "codes are the same in both hemispheres, but their seasons differ. "
        "When dates are omitted, the latest year in the filtered dataset is "
        "used."
    ),
    responses=_ANALYTICS_RESPONSES,
)
async def get_seasonal(
    filters: Annotated[FireFilters, Query()],
    service: Annotated[SeasonalService, Depends(get_seasonal_service)],
) -> SeasonalResponse:
    return await service.get_seasonal(filters)


@router.get(
    "/comparison",
    response_model=ComparisonResponse,
    summary="Compare activity with prior-year baselines",
    description=(
        "Compare selected-period activity with prior-year totals grouped by "
        "calendar month or hemisphere-aware season. At least three prior years "
        "are required before historical statistics are returned. Insufficient "
        "history is reported explicitly. Observed periods must fall within a "
        "single calendar year."
    ),
    responses=_ANALYTICS_RESPONSES,
)
async def get_comparison(
    filters: Annotated[FireFilters, Query()],
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
    group_by: Annotated[
        Literal["month", "season"],
        Query(description="Historical grouping: month or hemisphere-aware season."),
    ] = "month",
) -> ComparisonResponse:
    return await service.compare(filters, group_by=group_by)


@router.get(
    "/anomalies",
    response_model=AnomalyResponse,
    summary="Robust monthly anomaly detection",
    description=(
        "Detect unusually high or low monthly activity using a median/MAD "
        "baseline from the same calendar month in prior years. The modified "
        "Z-score is 0.6745 * (observed - median) / MAD. Severity thresholds "
        "are >=2.5 moderate and >=3.5 high by default. At least three prior "
        "years are required. Zero MAD is reported as insufficient_variance "
        "unless the observation equals the median."
    ),
    responses=_ANALYTICS_RESPONSES,
)
async def get_anomalies(
    filters: Annotated[FireFilters, Query()],
    service: Annotated[AnomalyService, Depends(get_anomaly_service)],
) -> AnomalyResponse:
    return await service.detect(filters)
