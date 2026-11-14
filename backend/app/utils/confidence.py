"""Normalize mixed MODIS and VIIRS confidence values."""

from app.schemas.common import ConfidenceLevel


def normalize_confidence(sensor: str | None, raw_value: object) -> ConfidenceLevel:
    """Map a raw database confidence value to a stable bucket.

    MODIS values are numeric percentages: >=80 is high, 40-79 is nominal,
    and below 40 is low. VIIRS uses ``h``, ``n``, and ``l``. Unrecognized or
    missing values are preserved as ``unknown`` instead of being guessed.
    """
    if raw_value is None:
        return ConfidenceLevel.UNKNOWN

    raw_text = str(raw_value).strip()
    if not raw_text:
        return ConfidenceLevel.UNKNOWN

    sensor_name = (sensor or "").strip().upper()
    if sensor_name == "MODIS":
        try:
            numeric = float(raw_text)
        except ValueError:
            return ConfidenceLevel.UNKNOWN
        if numeric >= 80:
            return ConfidenceLevel.HIGH
        if numeric >= 40:
            return ConfidenceLevel.NOMINAL
        return ConfidenceLevel.LOW

    if sensor_name == "VIIRS":
        mapped = {
            "h": ConfidenceLevel.HIGH,
            "n": ConfidenceLevel.NOMINAL,
            "l": ConfidenceLevel.LOW,
        }
        return mapped.get(raw_text.lower(), ConfidenceLevel.UNKNOWN)

    return ConfidenceLevel.UNKNOWN
