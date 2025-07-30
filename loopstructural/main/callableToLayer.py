import numpy as np
from qgis.core import (
    QgsField,
    QgsRaster,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant


def callableToLayer(callable, layer, dtm, name: str):
    """Convert a feature to a raster and store it in QGIS as a temporary layer.

    :param feature: The object that has an `evaluate_value` method for computing values.
    :param dtm: Digital terrain model (if needed for processing).
    :param bounding_box: Object with `origin`, `maximum`, `step_vector`, and `nsteps`.
    :param crs: Coordinate reference system (QGIS CRS object).
    """
    layer.startEditing()
    if name not in [field.name() for field in layer.fields()]:
        layer.dataProvider().addAttributes([QgsField(name, QVariant.Double)])
        layer.updateFields()

    for feature in layer.getFeatures():
        geom = feature.geometry()
        points = []
        if geom.isMultipart():
            if geom.type() == QgsWkbTypes.PointGeometry:
                points = geom.asMultiPoint()
                # points = geom.asMultiPolyline()[0]
        else:
            if geom.type() == QgsWkbTypes.PointGeometry:
                points = [geom.asPoint()]

        for p in points:
            x = p.x()
            y = p.y()
            z = 0

            if dtm is not None:
                # Replace with your coordinates

                # Extract the value at the point
                z_value = dtm.dataProvider().identify(p, QgsRaster.IdentifyFormatValue)
                if z_value.isValid():
                    z = z_value.results()[1]
            value = callable(np.array([[x, y, z]]))
            feature[name] = value
        layer.commitChanges()
        layer.updateFields()
