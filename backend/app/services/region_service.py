"""Business logic for dynamically derived regions."""

from app.repositories.region_repository import RegionRepository
from app.schemas.region import (
    BoundingBox,
    Centroid,
    RegionListResponse,
    RegionRecord,
)
from app.utils.seasons import hemisphere_for_latitude


class RegionService:
    """Turn country aggregates into region response models."""

    def __init__(self, repository: RegionRepository) -> None:
        self.repository = repository

    async def list_regions(self) -> RegionListResponse:
        rows = await self.repository.list_regions()
        records: list[RegionRecord] = []

        for row in rows:
            centroid_latitude = row.get("centroid_latitude")
            centroid_longitude = row.get("centroid_longitude")
            bbox_values = (
                row.get("min_latitude"),
                row.get("min_longitude"),
                row.get("max_latitude"),
                row.get("max_longitude"),
            )
            has_bbox = all(value is not None for value in bbox_values)
            has_centroid = (
                centroid_latitude is not None and centroid_longitude is not None
            )

            records.append(
                RegionRecord(
                    id=row["country_code"],
                    country_code=row["country_code"],
                    name=row["country_name"] or row["country_code"],
                    continent=row.get("continent"),
                    hemisphere=(
                        hemisphere_for_latitude(float(centroid_latitude))
                        if has_centroid
                        else None
                    ),
                    hotspot_count=int(row["hotspot_count"]),
                    bounding_box=(
                        BoundingBox(
                            min_latitude=float(bbox_values[0]),
                            min_longitude=float(bbox_values[1]),
                            max_latitude=float(bbox_values[2]),
                            max_longitude=float(bbox_values[3]),
                        )
                        if has_bbox
                        else None
                    ),
                    centroid=(
                        Centroid(
                            latitude=float(centroid_latitude),
                            longitude=float(centroid_longitude),
                        )
                        if has_centroid
                        else None
                    ),
                )
            )

        return RegionListResponse(data=records, total=len(records))
