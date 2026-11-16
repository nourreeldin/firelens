"""Read-only fire detection endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.api.dependencies import get_fire_service
from app.schemas.fire import FireListQuery, FireListResponse, FireRecord
from app.services.fire_service import FireService

router = APIRouter(prefix="/fires", tags=["fires"])


@router.get(
    "",
    response_model=FireListResponse,
    summary="List fire detections",
    description=(
        "Return standardized raw satellite detections from public.fire_hotspots with "
        "date, country, sensor, bounding-box, and pagination filters. The "
        "bounding box is evaluated with PostGIS ST_Intersects and "
        "ST_MakeEnvelope."
    ),
    responses={404: {"description": "The requested region code was not found."}},
)
async def list_fires(
    query: Annotated[FireListQuery, Query()],
    service: Annotated[FireService, Depends(get_fire_service)],
) -> FireListResponse:
    return await service.list_fires(query)


@router.get(
    "/{fire_id}",
    response_model=FireRecord,
    summary="Get one fire detection",
    responses={404: {"description": "Fire detection not found."}},
)
async def get_fire(
    fire_id: Annotated[int, Path(ge=1)],
    service: Annotated[FireService, Depends(get_fire_service)],
) -> FireRecord:
    return await service.get_fire(fire_id)
