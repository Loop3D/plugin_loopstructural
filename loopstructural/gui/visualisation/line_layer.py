"""Read the line of a cross-section from a QGIS line layer."""

from typing import Optional

import numpy as np
from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsProject, QgsWkbTypes


def line_xy_from_layer(layer, target_crs=None) -> Optional[np.ndarray]:
    """Return an (M, 2) array of the vertices of the first line of a layer.

    The line is the first selected feature, or the first feature if nothing is
    selected. It is reprojected to ``target_crs`` if this is valid. The result
    is None if the layer has no usable line.
    """
    features = (
        list(layer.getSelectedFeatures())
        if layer.selectedFeatureCount() > 0
        else list(layer.getFeatures())
    )
    if not features:
        return None
    geom = features[0].geometry()
    if geom is None or geom.isEmpty():
        return None

    source_crs = layer.sourceCrs()
    if (
        target_crs is not None
        and target_crs.isValid()
        and source_crs.isValid()
        and source_crs != target_crs
    ):
        geom = QgsGeometry(geom)
        geom.transform(QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance()))

    if QgsWkbTypes.isMultiType(geom.wkbType()):
        parts = geom.asMultiPolyline()
        polyline = parts[0] if parts else []
    else:
        polyline = geom.asPolyline()
    if len(polyline) < 2:
        return None
    return np.array([[pt.x(), pt.y()] for pt in polyline])
