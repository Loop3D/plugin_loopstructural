"""Choose the number of interpolation elements from the data of a feature.

The module does not import QGIS, so the tests run in the fast tests/unit/ job.
"""

from dataclasses import dataclass

import numpy as np

MIN_NELEMENTS = 5_000
MAX_NELEMENTS = 250_000
ROUND_TO = 1_000
ELEMENTS_PER_EQUATION = 25
MAX_SURFACES = 10
SURFACE_STEP = 0.1


@dataclass
class DataSummary:
    """The measures of the data of one feature.

    `spread` is 0 for parallel planes and 1 for orientations in all
    directions.
    """

    n_value: int = 0
    n_orientation: int = 0
    n_surfaces: int = 0
    spread: float = 0.0


def _normals_from_strike_dip(strike, dip) -> np.ndarray:
    """Return the unit normals of planes (right-hand rule strike, dip in degrees)."""
    strike = np.radians(np.asarray(strike, dtype=float))
    dip = np.radians(np.asarray(dip, dtype=float))
    dip_direction = strike + np.pi / 2
    return np.column_stack(
        [
            -np.sin(dip) * np.sin(dip_direction),
            -np.sin(dip) * np.cos(dip_direction),
            np.cos(dip),
        ]
    )


def orientation_spread(normals) -> float:
    """Return the spread of orientations: 0 (parallel) to 1 (all directions).

    The sign of a normal does not change the result: the measure uses the
    largest eigenvalue of the mean orientation tensor, which is 1 for parallel
    planes and 1/3 for uniform directions.
    """
    normals = np.asarray(normals, dtype=float).reshape(-1, 3)
    normals = normals[np.all(np.isfinite(normals), axis=1)]
    lengths = np.linalg.norm(normals, axis=1)
    normals = normals[lengths > 0] / lengths[lengths > 0, None]
    if len(normals) < 2:
        return 0.0
    tensor = normals.T @ normals / len(normals)
    largest = np.linalg.eigvalsh(tensor)[-1]
    return float(np.clip((1.0 - largest) / (2.0 / 3.0), 0.0, 1.0))


def _has(df, columns) -> np.ndarray:
    """Return a mask of the rows where all `columns` exist and are not NaN."""
    mask = np.ones(len(df), dtype=bool)
    for column in columns:
        if column not in df.columns:
            return np.zeros(len(df), dtype=bool)
        mask &= df[column].notna().to_numpy()
    return mask


def summarise_data(df) -> DataSummary:
    """Return the `DataSummary` of a feature data frame (or None for no data).

    Value, interface and inequality rows are value constraints. Rows with a
    normal (nx, ny, nz or gx, gy, gz), a strike and a dip, or a tangent (tx,
    ty, tz) are orientation constraints.
    """
    if df is None or len(df) == 0:
        return DataSummary()
    value = _has(df, ['val']) | _has(df, ['interface']) | _has(df, ['l', 'u'])
    normal = _has(df, ['nx', 'ny', 'nz'])
    gradient = _has(df, ['gx', 'gy', 'gz']) & ~normal
    strike_dip = _has(df, ['strike', 'dip']) & ~normal & ~gradient
    tangent = _has(df, ['tx', 'ty', 'tz'])
    orientation = normal | gradient | strike_dip | tangent

    vectors = []
    if normal.any():
        vectors.append(df.loc[normal, ['nx', 'ny', 'nz']].to_numpy(dtype=float))
    if gradient.any():
        vectors.append(df.loc[gradient, ['gx', 'gy', 'gz']].to_numpy(dtype=float))
    if strike_dip.any():
        vectors.append(
            _normals_from_strike_dip(
                df.loc[strike_dip, 'strike'].to_numpy(), df.loc[strike_dip, 'dip'].to_numpy()
            )
        )
    spread = orientation_spread(np.vstack(vectors)) if vectors else 0.0

    n_surfaces = 0
    if _has(df, ['val']).any():
        n_surfaces = int(df.loc[_has(df, ['val']), 'val'].nunique())
    if 'interface' in df.columns and df['interface'].notna().any():
        n_surfaces = max(n_surfaces, int(df['interface'].nunique()))
    return DataSummary(
        n_value=int(value.sum()),
        n_orientation=int(orientation.sum()),
        n_surfaces=n_surfaces,
        spread=spread,
    )


def suggest_nelements(summary: DataSummary) -> int:
    """Return the number of elements for a feature with the data `summary`.

    elements = equations x 25 x surface factor x spread factor, where an
    orientation is two equations, the surface factor is 1 + 0.1 for each
    surface after the first (at most 10 surfaces) and the spread factor is
    1 + spread. The result is rounded to 1 000 and limited to 5 000 .. 250 000.
    """
    equations = summary.n_value + 2 * summary.n_orientation
    if equations <= 0:
        return MIN_NELEMENTS
    surfaces = min(max(summary.n_surfaces, 1), MAX_SURFACES)
    surface_factor = 1 + SURFACE_STEP * (surfaces - 1)
    spread_factor = 1 + min(max(summary.spread, 0.0), 1.0)
    elements = equations * ELEMENTS_PER_EQUATION * surface_factor * spread_factor
    elements = int(round(elements / ROUND_TO)) * ROUND_TO
    return int(min(max(elements, MIN_NELEMENTS), MAX_NELEMENTS))
