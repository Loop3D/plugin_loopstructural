import numpy as np
from qgis.core import (
    QgsField,
    QgsRaster,
    QgsWkbTypes,
)

from loopstructural.gui.compatibility import QVariantCompat


def callableToLayer(callable, layer, dtm, name: str):
    """Convert a feature to a raster and store it in QGIS as a temporary layer.

    Parameters
    ----------
    callable : callable
        A callable that accepts an (N,3) numpy array of points and returns values.
    layer : QgsVectorLayer
        QGIS vector layer to update with computed values.
    dtm : QgsRaster or None
        Digital terrain model used to extract Z values for points (optional).
    name : str
        Name of the attribute/field to store the computed values.

    Returns
    -------
    None
        The function updates the provided `layer` in-place.
    """
    layer.startEditing()
    if name not in [field.name() for field in layer.fields()]:
        layer.dataProvider().addAttributes([QgsField(name, QVariantCompat.Double)])
        layer.updateFields()
    field_idx = layer.fields().indexFromName(name)

    for feature in layer.getFeatures():
        geom = feature.geometry()
        points = []
        if geom.isMultipart():
            if geom.type() == QgsWkbTypes.PointGeometry:
                points = geom.asMultiPoint()
        else:
            if geom.type() == QgsWkbTypes.PointGeometry:
                points = [geom.asPoint()]

        for p in points:
            x = p.x()
            y = p.y()
            z = 0

            if dtm is not None:
                # Extract the value at the point
                z_value = dtm.dataProvider().identify(p, QgsRaster.IdentifyFormatValue)
                if z_value.isValid():
                    z = z_value.results()[1]
            value = callable(np.array([[x, y, z]]))
            # feature[name] = value only mutates the local QgsFeature copy
            # returned by getFeatures() -- it doesn't persist to the layer.
            # changeAttributeValue is what actually registers the edit.
            layer.changeAttributeValue(feature.id(), field_idx, value)

    layer.commitChanges()
    layer.updateFields()
