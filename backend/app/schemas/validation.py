"""Request and response models for validation reports."""

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValidationFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    region_pk: int | None = Field(default=None, gt=0)
    method_version: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = Field(
        default=None,
        description="Only reports whose validation period overlaps this date are returned.",
    )
    end_date: date | None = Field(
        default=None,
        description="Only reports whose validation period overlaps this date are returned.",
    )

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be earlier than or equal to end_date")
        return self


class ValidationRecord(BaseModel):
    id: int
    region_id: int | None = Field(
        description="Integer public.regions.id; null means no region assignment."
    )
    country_code: str | None = None
    method_version: str
    validation_period_start: date | None = None
    validation_period_end: date | None = None
    mae: float | None = Field(default=None, ge=0)
    rmse: float | None = Field(default=None, ge=0)
    bias: float | None = None
    sample_size: int | None = Field(default=None, ge=0)
    notes: str | None = None
    created_at: datetime


class ValidationPagination(BaseModel):
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    total: int = Field(ge=0)


class ValidationListResponse(BaseModel):
    status: Literal["ok"]
    data: list[ValidationRecord]
    pagination: ValidationPagination
