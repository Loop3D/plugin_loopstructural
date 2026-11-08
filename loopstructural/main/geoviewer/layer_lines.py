"""Read the lines of the project layers (fault traces and basal contacts) for a push.

This module imports QGIS, so it runs on the main thread: QGIS layers are not
safe to read from a background task. The result is plain numpy arrays.
"""

from typing import Callable, List, Optional

import numpy as np
from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsProject, QgsWkbTypes

from .scene import LineSet


def polylines_from_layer(
    layer,
    target_crs=None,
    z_function: Optional[Callable[[float, float], float]] = None,
    use_z: bool = False,
) -> List[np.ndarray]:
    """Return one (n, 3) array for each line of a line layer.

    Parameters
    ----------
    layer : a QGIS vector layer
        Features that are not lines are ignored.
    target_crs : QgsCoordinateReferenceSystem, optional
        The CRS of the model. The lines are reprojected to it when it is valid.
    z_function : callable, optional
        ``z_function(x, y)`` gives the elevation, for a line with no z value.
    use_z : bool
        Use the z values of the geometry when it has them.
    """
    transform = None
    source_crs = layer.sourceCrs()
    if (
        target_crs is not None
        and target_crs.isValid()
        and source_crs.isValid()
        and source_crs != target_crs
    ):
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    lines = []
    for feature in layer.getFeatures():
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        if QgsWkbTypes.geometryType(geometry.wkbType()) != QgsWkbTypes.GeometryType.LineGeometry:
            continue
        if transform is not None:
            geometry = QgsGeometry(geometry)
            geometry.transform(transform)
        abstract = geometry.constGet()
        parts = [abstract.geometryN(i) for i in range(abstract.numGeometries())]
        for part in parts:
            rows = []
            for vertex in part.vertices():
                z = vertex.z() if use_z and vertex.is3D() else float('nan')
                if np.isnan(z):
                    z = float(z_function(vertex.x(), vertex.y())) if z_function else 0.0
                rows.append((vertex.x(), vertex.y(), z))
            if len(rows) >= 2:
                lines.append(np.array(rows, dtype=float))
    return lines


def collect_line_sets(data_manager, model_manager) -> List[LineSet]:
    """Return the lines of the fault trace layer and of the basal contact layer.

    A layer that is not set, or that has no line, is left out.
    """
    if data_manager is None:
        return []
    crs = data_manager.get_model_crs()
    z_function = getattr(model_manager, 'dem_function', None)
    sources = (
        ('fault_traces', 'Fault traces', data_manager.get_fault_traces()),
        ('basal_contacts', 'Basal contacts', data_manager.get_basal_contacts()),
    )
    result = []
    for key, name, config in sources:
        layer = (config or {}).get('layer')
        if layer is None:
            continue
        lines = polylines_from_layer(
            layer, crs, z_function, use_z=bool((config or {}).get('use_z_coordinate'))
        )
        if lines:
            result.append(LineSet(key, name, lines))
    return result
