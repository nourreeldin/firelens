"""Business logic for reading fire detections."""

from app.core.config import Settings
from app.core.exceptions import FireNotFoundError
from app.repositories.fire_repository import FireRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.fire import (
    FireListQuery,
    FireListResponse,
    FireRecord,
    Pagination,
)
from app.services.common import ensure_region_exists
from app.utils.fire_rows import normalize_fire_row


class FireService:
    """Read-only detection queries."""

    def __init__(
        self,
        repository: FireRepository,
        region_repository: RegionRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.region_repository = region_repository
        self.settings = settings

    async def list_fires(self, query: FireListQuery) -> FireListResponse:
        await ensure_region_exists(query, self.region_repository)

        limit = min(query.limit, self.settings.max_page_size)
        rows, total = await self.repository.list(
            query,
            limit=limit,
            offset=query.offset,
        )
        return FireListResponse(
            data=[self._to_record(row) for row in rows],
            pagination=Pagination(
                limit=limit,
                offset=query.offset,
                total=total,
            ),
        )

    async def get_fire(self, fire_id: int) -> FireRecord:
        row = await self.repository.get(fire_id)
        if row is None:
            raise FireNotFoundError(f"Fire detection {fire_id} was not found.")
        return self._to_record(row)

    @staticmethod
    def _to_record(row: dict) -> FireRecord:
        return FireRecord.model_validate(normalize_fire_row(row))
