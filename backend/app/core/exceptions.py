"""Application-specific exceptions translated by the API error handlers."""


class FireLensError(Exception):
    """Base class for expected application errors."""


class FireNotFoundError(FireLensError, LookupError):
    """Raised when a requested detection does not exist."""


class RegionNotFoundError(FireLensError, LookupError):
    """Raised when a region code does not exist in the dataset."""


class DateRangeError(FireLensError, ValueError):
    """Raised when a requested date range is invalid."""


class DatabaseUnavailableError(FireLensError, RuntimeError):
    """Raised when a database connection cannot be acquired or is lost."""


class DatabaseExecutionError(FireLensError, RuntimeError):
    """Raised when a database query fails."""
