"""Pydantic schemas for dynamically derived regions."""

from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Geographic extent of a derived country region."""

    min_latitude: float = Field(ge=-90, le=90)
    min_longitude: float = Field(ge=-180, le=180)
    max_latitude: float = Field(ge=-90, le=90)
    max_longitude: float = Field(ge=-180, le=180)


class Centroid(BaseModel):
    """Geographic centroid of the hotspot geometries in a region."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RegionRecord(BaseModel):
    """Country-level region derived from the canonical hotspot table."""

    id: str = Field(
        min_length=3,
        max_length=3,
        description="Three-letter country code used as the region identifier.",
    )
    country_code: str = Field(min_length=3, max_length=3)
    name: str
    continent: str | None = None
    hemisphere: Literal["northern", "southern"] | None = None
    hotspot_count: int = Field(ge=0)
    bounding_box: BoundingBox | None = None
    centroid: Centroid | None = None


class RegionListResponse(BaseModel):
    """All regions currently represented in the canonical dataset."""

    data: list[RegionRecord]
    total: int = Field(ge=0)
