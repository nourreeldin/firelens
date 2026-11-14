"""CSV output safety helpers."""

# Spreadsheet applications can interpret these leading characters as formulas.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_value(value: object) -> object:
    """Neutralize spreadsheet formula injection while preserving numeric types."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if stripped.startswith(_FORMULA_PREFIXES) or value.startswith(("\t", "\r")):
        return f"'{value}"
    return value
