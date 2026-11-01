"""The map preview of one feature: isolines of its scalar field.

The scalar field is evaluated on a regular grid over the model area. Each
point has the Z of the DEM, so the lines are the trace of the surfaces on the
ground, as on a geological map.

This module does not import QGIS, so the unit tests can run it.
"""

from typing import Callable, List, Optional, Tuple

import numpy as np

DEFAULT_RESOLUTION = 150
DEFAULT_LEVEL_COUNT = 10


def grid_points(
    origin, maximum, resolution: int, dem_function: Optional[Callable] = None
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the grid of the preview.

    Parameters
    ----------
    origin, maximum : sequence of float
        The lower and the upper corner of the model area. Only X and Y are used.
    resolution : int
        The number of points along each side.
    dem_function : callable, optional
        ``dem_function(x, y)`` gives the Z of the ground. Without it, Z is 0.

    Returns
    -------
    x, y : numpy.ndarray
        The coordinates along each side, with shape ``(resolution,)``.
    points : numpy.ndarray
        The points, with shape ``(resolution * resolution, 3)``. The order is
        row by row: the first ``resolution`` points have the first Y.
    """
    if resolution < 2:
        raise ValueError("The resolution must be 2 or more.")
    x = np.linspace(origin[0], maximum[0], resolution)
    y = np.linspace(origin[1], maximum[1], resolution)
    xx, yy = np.meshgrid(x, y)
    if dem_function is None:
        zz = np.zeros_like(xx)
    else:
        zz = np.vectorize(dem_function, otypes=[float])(xx, yy)
    points = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    return x, y, points


def default_levels(values, count: int = DEFAULT_LEVEL_COUNT) -> np.ndarray:
    """Return ``count`` levels, spaced evenly between the lowest and the highest value.

    The lowest and the highest value are not levels, because a line there is a
    point or an edge. An empty array means that the field has no range.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0 or count < 1:
        return np.array([])
    low, high = values.min(), values.max()
    if not high > low:
        return np.array([])
    return np.linspace(low, high, count + 2)[1:-1]


def isolines(x, y, values, levels) -> List[Tuple[float, np.ndarray]]:
    """Return the lines of the field ``values`` at each level.

    Parameters
    ----------
    x, y : array_like
        The coordinates along each side of the grid.
    values : array_like
        The field, with shape ``(len(y), len(x))``. A value that is not finite
        is a gap: no line crosses it.
    levels : iterable of float
        The levels of the lines.

    Returns
    -------
    list of tuple
        ``(level, coordinates)`` for each line. ``coordinates`` has shape
        ``(n, 2)`` with X and Y.
    """
    try:
        import contourpy
    except ImportError as err:  # pragma: no cover - contourpy comes with matplotlib
        raise RuntimeError("The preview needs the contourpy package (part of matplotlib).") from err
    values = np.asarray(values, dtype=float)
    if values.shape != (len(y), len(x)):
        raise ValueError("values must have the shape (len(y), len(x)).")
    generator = contourpy.contour_generator(
        np.asarray(x, dtype=float),
        np.asarray(y, dtype=float),
        np.ma.masked_invalid(values),
    )
    lines = []
    for level in levels:
        for line in generator.lines(float(level)):
            line = np.asarray(line, dtype=float)
            if len(line) >= 2:
                lines.append((float(level), line))
    return lines
