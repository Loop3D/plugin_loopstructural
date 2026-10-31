"""Isosurface values: parse the user input and check it against the range of a
scalar field. No Qt code.
"""

import re
from typing import Iterable, List, Sequence, Tuple

import numpy as np

# Values that differ by less than this (relative to the range) are the same value
_REL_TOLERANCE = 1e-9


def unique_values(values: Iterable[float]) -> List[float]:
    """Remove repeated values and keep the first occurrence of each."""
    result: List[float] = []
    for value in values:
        value = float(value)
        if not np.isfinite(value):
            continue
        if not any(np.isclose(value, v, rtol=_REL_TOLERANCE, atol=_REL_TOLERANCE) for v in result):
            result.append(value)
    return result


def values_from_list(text: str) -> List[float]:
    """Read values separated by commas, semicolons or spaces.

    Raises ValueError if a part of the text is not a number. Repeated values
    are removed.
    """
    parts = [p for p in re.split(r'[,;\s]+', text.strip()) if p]
    if not parts:
        raise ValueError("Enter at least one value")
    values = []
    for part in parts:
        try:
            value = float(part)
        except ValueError:
            raise ValueError(f"'{part}' is not a number") from None
        if not np.isfinite(value):
            raise ValueError(f"'{part}' is not a finite number")
        values.append(value)
    return unique_values(values)


def values_from_range(start: float, end: float, count: int) -> List[float]:
    """Return `count` values from `start` to `end`, with equal steps.

    One value gives `start`. Raises ValueError if `count` is less than 1.
    """
    if count < 1:
        raise ValueError("The count must be 1 or more")
    if count == 1:
        return [float(start)]
    return unique_values(np.linspace(start, end, count))


def default_range_values(low: float, high: float, count: int = 5) -> List[float]:
    """Values that are inside the range of a scalar field, with equal steps.

    The values are not at the minimum or the maximum of the field, where an
    isosurface has no geometry. Raises ValueError for an empty range.
    """
    if count < 1:
        raise ValueError("The count must be 1 or more")
    if not (np.isfinite(low) and np.isfinite(high)) or high <= low:
        raise ValueError("The scalar field has no range of values")
    return [float(v) for v in np.linspace(low, high, count + 2)[1:-1]]


def split_by_range(
    values: Sequence[float], low: float, high: float
) -> Tuple[List[float], List[float]]:
    """Split the values into (inside, outside) the range [low, high]."""
    inside, outside = [], []
    for value in values:
        (inside if low <= value <= high else outside).append(float(value))
    return inside, outside


def isosurface_name(feature_name: str, value: float) -> str:
    """The object name of an isosurface, for example `Fault_1_iso_0.50`."""
    return f'{feature_name}_iso_{value:.2f}'
