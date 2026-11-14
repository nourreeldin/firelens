"""Hemisphere-aware meteorological season helpers."""

from datetime import date

NORTHERN_SEASON_NAMES = {
    "DJF": "Winter",
    "MAM": "Spring",
    "JJA": "Summer",
    "SON": "Autumn",
}

SOUTHERN_SEASON_NAMES = {
    "DJF": "Summer",
    "MAM": "Autumn",
    "JJA": "Winter",
    "SON": "Spring",
}

SEASON_MONTHS = {
    "DJF": (12, 1, 2),
    "MAM": (3, 4, 5),
    "JJA": (6, 7, 8),
    "SON": (9, 10, 11),
}


def hemisphere_for_latitude(latitude: float) -> str:
    """Classify a latitude as northern or southern.

    The equator (0.0) is grouped with the northern hemisphere. The database
    dataset has no hotspot exactly on the equator, but documenting the edge
    case keeps the grouping deterministic.
    """
    return "southern" if latitude < 0 else "northern"


def season_code_for_month(month: int) -> str:
    """Return the meteorological season code for a calendar month."""
    if month in (12, 1, 2):
        return "DJF"
    if month in (3, 4, 5):
        return "MAM"
    if month in (6, 7, 8):
        return "JJA"
    if month in (9, 10, 11):
        return "SON"
    raise ValueError(f"Invalid month: {month}")


def season_year_for(year: int, month: int) -> int:
    """Assign December to the DJF season that ends in the following year."""
    if month == 12:
        return year + 1
    return year


def season_label(season: str, hemisphere: str) -> str:
    """Return the hemisphere-specific name for a season code."""
    names = SOUTHERN_SEASON_NAMES if hemisphere == "southern" else NORTHERN_SEASON_NAMES
    try:
        return f"{names[season]} ({season})"
    except KeyError as exc:
        raise ValueError(f"Invalid season code: {season}") from exc


def month_name(month: int) -> str:
    """Return the English name for a 1-based month number."""
    return date(2000, month, 1).strftime("%B")
