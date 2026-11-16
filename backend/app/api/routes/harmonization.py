"""Read-only endpoints for harmonized activity and its analytics."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_harmonization_service
from app.schemas.activity import (
    ActivityCalendarResponse,
    ActivityFilters,
    ActivityListResponse,
    HarmonizedAnomalyResponse,
    HarmonizedComparisonResponse,
    HarmonizedSeasonalResponse,
)
from app.services.harmonization_service import HarmonizationService

router = APIRouter(prefix="/harmonization", tags=["harmonization"])

_RESPONSES = {
    404: {"description": "The requested integer region primary key was not found."},
    422: {"description": "Invalid date range, filter, or pagination value."},
}


@router.get(
    "",
    response_model=ActivityListResponse,
    summary="List corrected harmonized activity",
    description=(
        "Return paginated grid/day activity from public.harmonized_activity. "
        "Use region_pk for the integer public.regions.id; the raw-fire "
        "region_id country-code filter is unchanged."
    ),
    responses=_RESPONSES,
)
async def list_harmonized_activity(
    filters: Annotated[ActivityFilters, Query()],
    service: Annotated[HarmonizationService, Depends(get_harmonization_service)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ActivityListResponse:
    return await service.list_activity(filters, limit=limit, offset=offset)


@router.get(
    "/calendar",
    response_model=ActivityCalendarResponse,
    summary="Daily harmonized activity calendar",
    description=(
        "Keep /api/v1/calendar for raw detection counts. This endpoint sums "
        "harmonized_count and MODIS/VIIRS counts across matching grid records, "
        "separately for each method_version. Multi-grid uncertainty is null "
        "until a scientifically approved aggregation rule is defined. Defaults "
        "to the latest 30 days represented by the filtered data."
    ),
    responses=_RESPONSES,
)
async def harmonized_calendar(
    filters: Annotated[ActivityFilters, Query()],
    service: Annotated[HarmonizationService, Depends(get_harmonization_service)],
) -> ActivityCalendarResponse:
    return await service.calendar(filters)


@router.get(
    "/analytics/seasonal",
    response_model=HarmonizedSeasonalResponse,
    summary="Monthly and meteorological-season harmonized activity",
    description=(
        "Return corrected activity totals by month and DJF/MAM/JJA/SON. "
        "Totals are separated by method_version. Harmonized rows do not carry "
        "latitude, so this endpoint returns season codes without the "
        "hemisphere-specific names used by raw-fire seasonal analytics."
    ),
    responses=_RESPONSES,
)
async def harmonized_seasonal(
    filters: Annotated[ActivityFilters, Query()],
    service: Annotated[HarmonizationService, Depends(get_harmonization_service)],
) -> HarmonizedSeasonalResponse:
    return await service.seasonal(filters)


@router.get(
    "/analytics/comparison",
    response_model=HarmonizedComparisonResponse,
    summary="Compare harmonized monthly activity with prior years",
    description=(
        "Compare selected-year monthly corrected activity against full-month "
        "totals from earlier years of the same method_version. The selected "
        "period must fit within one calendar year. At least three prior years "
        "are required by default; unavailable statistics remain null."
    ),
    responses=_RESPONSES,
)
async def harmonized_comparison(
    filters: Annotated[ActivityFilters, Query()],
    service: Annotated[HarmonizationService, Depends(get_harmonization_service)],
) -> HarmonizedComparisonResponse:
    return await service.comparison(filters)


@router.get(
    "/analytics/anomalies",
    response_model=HarmonizedAnomalyResponse,
    summary="Detect anomalies in harmonized monthly activity",
    description=(
        "Use the median and median absolute deviation of the same calendar "
        "month and method_version in prior years. The modified Z-score is "
        "0.6745 * (observed - median) / MAD. Zero MAD is reported explicitly; "
        "no score is fabricated when the scale is zero."
    ),
    responses=_RESPONSES,
)
async def harmonized_anomalies(
    filters: Annotated[ActivityFilters, Query()],
    service: Annotated[HarmonizationService, Depends(get_harmonization_service)],
) -> HarmonizedAnomalyResponse:
    return await service.anomalies(filters)
