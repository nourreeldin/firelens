"""Read-only dynamically derived region endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_region_service
from app.schemas.region import RegionListResponse
from app.services.region_service import RegionService

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get(
    "",
    response_model=RegionListResponse,
    summary="List countries represented in the dataset",
    description=(
        "Regions are derived at query time from distinct country_code values "
        "in public.fire_hotspots. Counts, bounding boxes, and centroids are "
        "computed with PostGIS."
    ),
)
async def list_regions(
    service: Annotated[RegionService, Depends(get_region_service)],
) -> RegionListResponse:
    return await service.list_regions()
