"""Read-only dynamically derived region endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_region_service
from app.schemas.region import RegionCatalogResponse, RegionListResponse
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


@router.get(
    "/catalog",
    response_model=RegionCatalogResponse,
    summary="List configured integer-ID regions",
    description=(
        "Return persisted rows from public.regions. The integer ids are used "
        "by harmonized activity and validation records. The existing /regions "
        "endpoint remains the derived country list used by raw fire filters."
    ),
)
async def list_region_catalog(
    service: Annotated[RegionService, Depends(get_region_service)],
) -> RegionCatalogResponse:
    return await service.list_catalog()
