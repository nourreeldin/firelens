"""Pydantic schemas for fire detections."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ConfidenceLevel, FireFilters


class FireRecord(BaseModel):
    """One harmonized fire detection returned by the read-only API."""

    id: int
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    acq_date: date
    acq_time: int | None = Field(
        default=None,
        description="Original FIRMS acquisition time in HHMM format.",
    )
    acq_datetime_utc: datetime | None = None
    sensor: str | None = None
    confidence: ConfidenceLevel
    confidence_raw: str | None = Field(
        default=None,
        description="Original database confidence value before normalization.",
    )
    satellite: str | None = None
    version: str | None = None
    daynight: str | None = None
    brightness: float | None = None
    brightness_thermal: float | None = None
    scan: float | None = None
    track: float | None = None
    frp: float | None = None
    country_code: str | None = None
    country_name: str | None = None
    continent: str | None = None
    spatial_grid_id: str | None = None


class Pagination(BaseModel):
    """Offset pagination metadata."""

    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class FireListResponse(BaseModel):
    """Paginated fire detections."""

    data: list[FireRecord]
    pagination: Pagination


class FireListQuery(FireFilters):
    """Filters plus offset pagination for the detection list."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
