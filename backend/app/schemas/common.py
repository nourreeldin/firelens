"""Shared query models and normalized confidence types."""

from datetime import date
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Sensor(str, Enum):
    """Sensors present in the harmonized FIRMS dataset."""

    MODIS = "MODIS"
    VIIRS = "VIIRS"


class ConfidenceLevel(str, Enum):
    """Normalized confidence buckets shared by both sensors."""

    HIGH = "high"
    NOMINAL = "nominal"
    LOW = "low"
    UNKNOWN = "unknown"


class FireFilters(BaseModel):
    """Filters shared by detection, calendar, analytics, and export routes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    start_date: date | None = Field(
        default=None,
        description="Inclusive acquisition date lower bound.",
    )
    end_date: date | None = Field(
        default=None,
        description="Inclusive acquisition date upper bound.",
    )
    region_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z]{3}$",
        description="Three-letter country code, for example EGY or USA.",
    )
    sensor: Sensor | None = Field(
        default=None,
        description="Sensor name: MODIS or VIIRS (case-insensitive).",
    )

    min_latitude: float | None = Field(default=None, ge=-90, le=90)
    max_latitude: float | None = Field(default=None, ge=-90, le=90)
    min_longitude: float | None = Field(default=None, ge=-180, le=180)
    max_longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("region_id", mode="before")
    @classmethod
    def normalize_region_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("sensor", mode="before")
    @classmethod
    def normalize_sensor(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be earlier than or equal to end_date")

        bbox = (
            self.min_latitude,
            self.max_latitude,
            self.min_longitude,
            self.max_longitude,
        )
        provided = [value is not None for value in bbox]
        if any(provided) and not all(provided):
            raise ValueError(
                "min_latitude, max_latitude, min_longitude, and max_longitude "
                "must be provided together"
            )
        if all(provided):
            if self.min_latitude >= self.max_latitude:  # type: ignore[operator]
                raise ValueError("min_latitude must be less than max_latitude")
            if self.min_longitude >= self.max_longitude:  # type: ignore[operator]
                raise ValueError("min_longitude must be less than max_longitude")
        return self

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        """Return (min_lon, min_lat, max_lon, max_lat) for ST_MakeEnvelope."""
        if self.min_longitude is None:
            return None
        return (
            self.min_longitude,
            self.min_latitude,  # type: ignore[arg-type]
            self.max_longitude,  # type: ignore[arg-type]
            self.max_latitude,  # type: ignore[arg-type]
        )
