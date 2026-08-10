"""Small shared runtime-validation helpers."""

from __future__ import annotations

from math import isfinite
from numbers import Real


def validate_timestamp(
    timestamp: float,
    *,
    previous: float | None = None,
    name: str = "timestamp",
) -> float:
    """Return a finite timestamp that does not precede ``previous``."""

    if (
        not isinstance(timestamp, Real)
        or isinstance(timestamp, bool)
        or not isfinite(timestamp)
    ):
        raise ValueError(f"{name} must be finite")
    value = float(timestamp)
    if previous is not None and value < previous:
        raise ValueError(f"{name} must not move backwards")
    return value


def validate_positive_integer(value: int, *, name: str) -> int:
    """Return a positive integer, rejecting booleans explicitly."""

    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be an integer greater than zero")
    return value
