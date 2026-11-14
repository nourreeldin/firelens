"""FastAPI dependency factories for the raw-SQL service layer."""

from typing import Annotated

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.database import Database
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.fire_repository import FireRepository
from app.repositories.region_repository import RegionRepository
from app.services.anomaly_service import AnomalyService
from app.services.calendar_service import CalendarService
from app.services.comparison_service import ComparisonService
from app.services.export_service import ExportService
from app.services.fire_service import FireService
from app.services.region_service import RegionService
from app.services.seasonal_service import SeasonalService


def get_database(request: Request) -> Database:
    """Return the pool stored on the application during lifespan startup."""
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise DatabaseUnavailableError("Database is unavailable.")
    return database


def get_region_repository(
    database: Annotated[Database, Depends(get_database)],
) -> RegionRepository:
    return RegionRepository(database)


def get_fire_repository(
    database: Annotated[Database, Depends(get_database)],
) -> FireRepository:
    return FireRepository(database)


def get_analytics_repository(
    database: Annotated[Database, Depends(get_database)],
) -> AnalyticsRepository:
    return AnalyticsRepository(database)


def get_fire_service(
    repository: Annotated[FireRepository, Depends(get_fire_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FireService:
    return FireService(repository, region_repository, settings)


def get_region_service(
    repository: Annotated[RegionRepository, Depends(get_region_repository)],
) -> RegionService:
    return RegionService(repository)


def get_calendar_service(
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CalendarService:
    return CalendarService(repository, region_repository, settings)


def get_seasonal_service(
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
) -> SeasonalService:
    return SeasonalService(repository, region_repository)


def get_comparison_service(
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonService:
    return ComparisonService(repository, region_repository, settings)


def get_anomaly_service(
    repository: Annotated[AnalyticsRepository, Depends(get_analytics_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnomalyService:
    return AnomalyService(repository, region_repository, settings)


def get_export_service(
    repository: Annotated[FireRepository, Depends(get_fire_repository)],
    region_repository: Annotated[RegionRepository, Depends(get_region_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExportService:
    return ExportService(repository, region_repository, settings)
