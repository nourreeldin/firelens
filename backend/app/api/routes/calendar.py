"""Zero-filled daily detection calendar endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_calendar_service
from app.schemas.calendar import CalendarResponse
from app.schemas.common import FireFilters
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get(
    "",
    response_model=CalendarResponse,
    summary="Daily detection calendar",
    description=(
        "Return zero-filled daily counts generated in PostgreSQL. When dates "
        "are omitted, the latest 30 days represented by the filtered dataset "
        "are used. Date ranges are limited by MAX_CALENDAR_DAYS."
    ),
    responses={
        404: {"description": "The requested region code was not found."},
        422: {"description": "Invalid date range."},
    },
)
async def get_calendar(
    filters: Annotated[FireFilters, Query()],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarResponse:
    return await service.get_calendar(filters)
