"""Robust statistics helpers for anomaly detection."""

MODIFIED_Z_SCORE_FACTOR = 0.6745


def modified_z_score(
    observed: float, median: float, median_absolute_deviation: float
) -> float | None:
    """Return the Iglewicz-Hoaglin modified Z-score.

    ``0.6745 * (observed - median) / MAD``. When MAD is zero the score is
    undefined because there is no scale estimate; callers must report that
    condition explicitly rather than dividing by zero.
    """
    if median_absolute_deviation <= 0:
        return None
    return MODIFIED_Z_SCORE_FACTOR * (observed - median) / median_absolute_deviation


def anomaly_severity(
    score: float | None, *, moderate_threshold: float, high_threshold: float
) -> str | None:
    """Classify an absolute modified Z-score as normal, moderate, or high."""
    if score is None:
        return None
    absolute = abs(score)
    if absolute >= high_threshold:
        return "high"
    if absolute >= moderate_threshold:
        return "moderate"
    return "normal"


def percentage_difference(observed: float, baseline: float | None) -> float | None:
    """Return observed change versus baseline, or ``None`` when undefined."""
    if baseline is None or baseline == 0:
        return None
    return round(((observed - baseline) / baseline) * 100, 2)
