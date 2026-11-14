"""Health endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_database
from app.core.config import Settings, get_settings
from app.db.database import Database
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service and database health",
    responses={503: {"description": "Database is unavailable."}},
)
async def health(
    database: Annotated[Database, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Verify that the API can execute a read-only database query."""
    await database.check()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        database="connected",
    )
