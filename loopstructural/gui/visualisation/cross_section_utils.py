"""Pure-geometry helpers for building cross-section meshes.

No Qt/pyvista-viewer or QGIS dependency -- callers (e.g. FeatureListWidget)
sample points from the returned meshes and colour them via
`mesh_scalar_utils.stratigraphic_ids_to_rgb`.
"""

import numpy as np
import pyvista as pv


def build_plane_mesh(origin, normal, size: float, resolution: int = 50) -> pv.PolyData:
    """Build a square plane mesh centred at `origin`, oriented by `normal`.

    Parameters
    ----------
    origin : array_like
        (3,) plane centre.
    normal : array_like
        (3,) plane normal; does not need to be unit length.
    size : float
        Edge length of the (square) plane.
    resolution : int, optional
        Number of sample points along each edge, by default 50.
    """
    return pv.Plane(
        center=origin,
        direction=normal,
        i_size=size,
        j_size=size,
        i_resolution=resolution,
        j_resolution=resolution,
    )


def resample_polyline(coords_xy, n: int) -> np.ndarray:
    """Resample a 2D polyline to `n` points, evenly spaced by arc length."""
    coords = np.asarray(coords_xy, dtype=float)
    seg_lengths = np.hypot(*np.diff(coords, axis=0).T)
    cumulative = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    total_length = cumulative[-1]
    if total_length == 0:
        return np.repeat(coords[:1], n, axis=0)
    targets = np.linspace(0.0, total_length, n)
    x = np.interp(targets, cumulative, coords[:, 0])
    y = np.interp(targets, cumulative, coords[:, 1])
    return np.column_stack([x, y])


def build_line_extrusion_mesh(
    coords_xy, z_min: float, z_max: float, resolution: int = 50, z_resolution: int = 50
) -> pv.StructuredGrid:
    """Build a vertical cross-section by extruding a 2D line through a Z range.

    Parameters
    ----------
    coords_xy : array_like
        (M, 2) ordered line vertices, in the model's coordinate system.
    z_min, z_max : float
        Vertical extent of the extrusion.
    resolution : int, optional
        Number of points sampled along the line (by arc length), by default 50.
    z_resolution : int, optional
        Number of points sampled vertically, by default 50.
    """
    xy = resample_polyline(coords_xy, resolution)
    z = np.linspace(z_min, z_max, z_resolution)
    xx = np.tile(xy[:, 0][:, None], (1, z_resolution))
    yy = np.tile(xy[:, 1][:, None], (1, z_resolution))
    zz = np.tile(z[None, :], (resolution, 1))
    return pv.StructuredGrid(xx, yy, zz)
