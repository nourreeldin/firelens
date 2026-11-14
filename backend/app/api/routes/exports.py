"""Streaming CSV export endpoint."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.dependencies import get_export_service
from app.core.security import require_api_key
from app.schemas.common import FireFilters
from app.services.export_service import ExportService

router = APIRouter(
    prefix="/exports",
    tags=["exports"],
    dependencies=[Depends(require_api_key)],
)


@router.get(
    "/fires",
    summary="Export fire detections as CSV",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "Streamed CSV export of filtered detections.",
        },
        404: {"description": "The requested region code was not found."},
    },
)
async def export_fires(
    filters: Annotated[FireFilters, Query()],
    service: Annotated[ExportService, Depends(get_export_service)],
) -> StreamingResponse:
    """Stream filtered detections as a CSV attachment.

    Rows are read with an asyncpg server-side cursor and yielded in chunks, so
    the full result set is never materialized in memory. Text values beginning
    with spreadsheet formula characters are prefixed with an apostrophe.
    """
    stream = await service.prepare_export(filters)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"firelens_fires_{timestamp}.csv"

    return StreamingResponse(
        stream,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
