"""Pydantic schemas for the zero-filled detection calendar."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class CalendarDay(BaseModel):
    """Detection count for one calendar day."""

    date: date
    fire_count: int = Field(ge=0)


class CalendarMeta(BaseModel):
    """Period and filters represented by a calendar response."""

    start_date: date | None = None
    end_date: date | None = None
    total_days: int = Field(ge=0)
    total_fires: int = Field(ge=0)
    region_id: str | None = None
    sensor: str | None = None


class CalendarResponse(BaseModel):
    """Daily counts with explicit zeroes for days without detections."""

    status: Literal["ok", "no_data"]
    data: list[CalendarDay]
    meta: CalendarMeta
