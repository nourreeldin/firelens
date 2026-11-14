"""Lightweight optional API-key protection for the CSV export endpoint."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import Settings, get_settings

api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Shared API key. Only required when API_KEY is configured.",
)


async def require_api_key(
    header_value: Annotated[str | None, Security(api_key_header)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str | None:
    """Validate the configured API key.

    The API is open by default so local development and the public read-only
    prototype work without credentials. Setting ``API_KEY`` turns this
    dependency into a requirement for the CSV export.
    """
    expected_key = (
        settings.api_key.get_secret_value() if settings.api_key is not None else ""
    )
    if not expected_key:
        return None

    if header_value is None or not secrets.compare_digest(header_value, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return header_value
