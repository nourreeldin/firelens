"""Read-only validation report endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_validation_service
from app.schemas.validation import ValidationFilters, ValidationListResponse
from app.services.harmonization_service import ValidationService

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get(
    "",
    response_model=ValidationListResponse,
    summary="List harmonization validation reports",
    description=(
        "Return paginated validation reports with nullable metrics. "
        "region_pk is the integer public.regions.id. Date filters select "
        "reports whose validation periods overlap the requested range."
    ),
    responses={
        404: {"description": "The requested integer region primary key was not found."},
        422: {"description": "Invalid date filter or pagination value."},
    },
)
async def list_validation_reports(
    filters: Annotated[ValidationFilters, Query()],
    service: Annotated[ValidationService, Depends(get_validation_service)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ValidationListResponse:
    return await service.list_reports(filters, limit=limit, offset=offset)
