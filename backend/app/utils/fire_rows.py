"""Convert raw database rows into API-ready fire records."""

from typing import Any

from app.utils.confidence import normalize_confidence


def normalize_fire_row(row: dict[str, Any]) -> dict[str, Any]:
    """Add normalized and raw confidence values to a database row."""
    payload = dict(row)
    raw_confidence = payload.get("confidence")
    payload["confidence"] = normalize_confidence(payload.get("sensor"), raw_confidence)
    payload["confidence_raw"] = (
        str(raw_confidence) if raw_confidence is not None else None
    )
    return payload
