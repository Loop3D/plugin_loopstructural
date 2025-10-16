import pandas as pd
from qgis.core import QgsVectorLayer


class VectorLayerWrapper:
    def __init__(self, vector_layer: QgsVectorLayer):
        self.vector_layer = vector_layer

    def to_dataframe(self):
        features = self.vector_layer.getFeatures()
        attributes = [field.name() for field in self.vector_layer.fields()]
        data = []

        for feature in features:
            data.append(feature.attributes())

        df = pd.DataFrame(data, columns=attributes)
        return df
