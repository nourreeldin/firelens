"""Trusted SQL fragment builder for parameterized fire filters."""

from __future__ import annotations

from typing import Any

from app.schemas.common import FireFilters


class WhereBuilder:
    """Build a WHERE clause while numbering PostgreSQL placeholders safely.

    Clause templates contain ``{}`` placeholders. Only code-defined SQL
    fragments are interpolated; user values are always appended as asyncpg
    parameters.
    """

    def __init__(self, *, param_offset: int = 0) -> None:
        self._parts: list[str] = []
        self.params: list[Any] = []
        self._param_offset = param_offset

    def add(self, clause_template: str, *values: Any) -> WhereBuilder:
        placeholders: list[str] = []
        for value in values:
            self.params.append(value)
            placeholders.append(f"${self._param_offset + len(self.params)}")
        self._parts.append(clause_template.format(*placeholders))
        return self

    @property
    def where_sql(self) -> str:
        if not self._parts:
            return ""
        return "WHERE " + " AND ".join(self._parts)


def build_fire_filters(filters: FireFilters, *, param_offset: int = 0) -> WhereBuilder:
    """Translate shared API filters into parameterized SQL conditions."""
    builder = WhereBuilder(param_offset=param_offset)

    if filters.start_date is not None:
        builder.add("acq_date >= {}", filters.start_date)
    if filters.end_date is not None:
        builder.add("acq_date <= {}", filters.end_date)
    if filters.region_id is not None:
        builder.add("country_code = {}", filters.region_id)
    if filters.sensor is not None:
        builder.add("sensor = {}", filters.sensor.value)

    bbox = filters.bbox
    if bbox is not None:
        # Keep geom directly visible to its GiST index. Only missing geometries
        # use coordinates, and both OR branches remain under the other filters.
        builder.add(
            "((geom IS NOT NULL AND "
            "ST_Intersects(geom, ST_MakeEnvelope({0}, {1}, {2}, {3}, 4326))) "
            "OR (geom IS NULL AND "
            "ST_Intersects(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), "
            "ST_MakeEnvelope({0}, {1}, {2}, {3}, 4326))))",
            *bbox,
        )

    return builder
