from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsVectorLayer,
)


def line_to_point(input_layer_path, output_layer_path):
    # Load the input line layer
    line_layer = QgsVectorLayer(input_layer_path, "line_layer", "ogr")
    if not line_layer.isValid():
        print("Layer failed to load!")
        return

    # Create an empty point layer
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))
    point_layer = QgsVectorLayer("Point?crs=" + line_layer.crs().toWkt(), "point_layer", "memory")
    point_layer.dataProvider().addAttributes(fields)
    point_layer.updateFields()

    # Iterate over each feature in the line layer
    for feature in line_layer.getFeatures():
        geom = feature.geometry()
        if geom.isMultipart():
            points = geom.asMultiPolyline()
        else:
            points = [geom.asPolyline()]

        # Create a point feature for each vertex in the line
        for line in points:
            for point in line:
                point_feature = QgsFeature()
                point_feature.setGeometry(QgsGeometry.fromPointXY(QgsPoint(point)))
                point_feature.setAttributes([feature.id()])
                point_layer.dataProvider().addFeature(point_feature)

    return point_layer
