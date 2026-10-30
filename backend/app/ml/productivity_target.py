"""Productivity target transformation and calibration utilities.

Transforms genuine 1.0-5.0 user self-report feedback ratings into calibrated 0.0-100.0
productivity target scores for model training and evaluation.
"""

from typing import Optional


def transform_ratings_to_productivity_score(
    productivity_rating: float,
    *,
    focus_rating: Optional[float] = None,
    energy_rating: Optional[float] = None,
) -> float:
    """Transform genuine 1.0-5.0 user self-report feedback ratings into calibrated 0.0-100.0 productivity score.

    Mathematical Transformation:
    - Direct Productivity:
        calibrated_score = (productivity_rating - 1.0) * 25.0
        Mapping:
          1.0 -> 0.0
          2.0 -> 25.0
          3.0 -> 50.0
          4.0 -> 75.0
          5.0 -> 100.0

    - Multi-dimensional Composite (when focus and energy are provided):
        calibrated_score = (
            0.60 * (productivity_rating - 1.0) +
            0.25 * (focus_rating - 1.0) +
            0.15 * (energy_rating - 1.0)
        ) * 25.0

    Validates that all input ratings are finite numbers within [1.0, 5.0].
    Returns a score strictly bounded in [0.0, 100.0].
    """
    if not isinstance(productivity_rating, (int, float)) or isinstance(productivity_rating, bool):
        raise ValueError("productivity_rating must be a numeric value")
    if not (1.0 <= productivity_rating <= 5.0):
        raise ValueError(f"productivity_rating must be between 1.0 and 5.0, got {productivity_rating}")

    if focus_rating is not None:
        if not isinstance(focus_rating, (int, float)) or isinstance(focus_rating, bool):
            raise ValueError("focus_rating must be a numeric value")
        if not (1.0 <= focus_rating <= 5.0):
            raise ValueError(f"focus_rating must be between 1.0 and 5.0, got {focus_rating}")

    if energy_rating is not None:
        if not isinstance(energy_rating, (int, float)) or isinstance(energy_rating, bool):
            raise ValueError("energy_rating must be a numeric value")
        if not (1.0 <= energy_rating <= 5.0):
            raise ValueError(f"energy_rating must be between 1.0 and 5.0, got {energy_rating}")

    if focus_rating is not None and energy_rating is not None:
        raw_scaled = (
            0.60 * (productivity_rating - 1.0)
            + 0.25 * (focus_rating - 1.0)
            + 0.15 * (energy_rating - 1.0)
        ) * 25.0
    else:
        raw_scaled = (productivity_rating - 1.0) * 25.0

    return round(max(0.0, min(100.0, float(raw_scaled))), 2)
