"""The thickness calculator algorithm extracts basal contacts from geology.

When no basal contacts layer is given, the algorithm gets the basal contacts
from the geology layer and the stratigraphic column. The map2loop calculator
is replaced with a fake, so these tests examine only the data that the
algorithm gives to it.
"""

import unittest
from unittest.mock import patch

import pandas as pd
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.testing import start_app

from loopstructural.processing.algorithms.thickness_calculator import (
    ThicknessCalculatorAlgorithm,
)

MODULE = 'loopstructural.processing.algorithms.thickness_calculator'


class FakeCalculator:
    """Keep the arguments of compute and return a thickness for each unit."""

    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def compute(self, units, stratigraphic_order, basal_contacts, *args):
        FakeCalculator.calls.append({'kwargs': self.kwargs, 'basal_contacts': basal_contacts})
        return pd.DataFrame(
            {
                'name': list(units['name']),
                'ThicknessMean': 1.0,
                'ThicknessMedian': 1.0,
                'ThicknessStdDev': 0.0,
            }
        )


class TestThicknessFromGeology(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.qgs = start_app()

    def setUp(self):
        FakeCalculator.calls = []
        self.geology = self._geology()
        QgsProject.instance().addMapLayer(self.geology)

    def tearDown(self):
        QgsProject.instance().removeMapLayer(self.geology.id())

    def _geology(self):
        # Two blocks of the layers A, B and C (top to bottom). The first block
        # is at 0 <= x <= 100 and the second block is at 1000 <= x <= 1100.
        layer = QgsVectorLayer("Polygon?crs=EPSG:28350&field=unitname:string", "geology", "memory")
        features = []
        for x0 in (0, 1000):
            x1 = x0 + 100
            for name, (y0, y1) in {'A': (200, 300), 'B': (100, 200), 'C': (0, 100)}.items():
                feature = QgsFeature(layer.fields())
                feature.setAttribute('unitname', name)
                feature.setGeometry(
                    QgsGeometry.fromWkt(
                        f"POLYGON(({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"
                    )
                )
                features.append(feature)
        layer.dataProvider().addFeatures(features)
        return layer

    def _points(self, fields, values):
        layer = QgsVectorLayer(f"Point?crs=EPSG:28350&{fields}", "points", "memory")
        features = []
        for x, y, attributes in values:
            feature = QgsFeature(layer.fields())
            feature.setAttributes(attributes)
            feature.setGeometry(QgsGeometry.fromWkt(f"POINT({x} {y})"))
            features.append(feature)
        layer.dataProvider().addFeatures(features)
        return layer

    def _run(self, geology):
        structure = self._points("field=DIPDIR:double&field=DIP:double", [(50, 150, [90.0, 10.0])])
        sampled_contacts = self._points("field=unit:string", [(50, 200, ['A'])])
        algorithm = ThicknessCalculatorAlgorithm()
        algorithm.initAlgorithm()
        parameters = {
            'THICKNESS_CALCULATOR_TYPE': 0,
            'BOUNDING_BOX_TYPE': 0,
            'MAX_LINE_LENGTH': 1000,
            'GEOLOGY': geology,
            'UNIT_NAME_FIELD': 'unitname',
            'STRATIGRAPHIC_COLUMN': ['A', 'B', 'C'],
            'SAMPLED_CONTACTS': sampled_contacts,
            'STRUCTURE_DATA': structure,
            'ORIENTATION_TYPE': 0,
            'DIPDIR_FIELD': 'DIPDIR',
            'DIP_FIELD': 'DIP',
            'THICKNESS': QgsProcessing.TEMPORARY_OUTPUT,
        }
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        with patch(f'{MODULE}.InterpolatedStructure', FakeCalculator):
            algorithm.processAlgorithm(parameters, context, QgsProcessingFeedback())
        self.assertEqual(len(FakeCalculator.calls), 1)
        return FakeCalculator.calls[0]

    def _length(self, contacts, unit):
        return contacts[contacts['basal_unit'] == unit].geometry.length.sum()

    def test_contacts_from_geology_layer(self):
        call = self._run(self.geology)
        contacts = call['basal_contacts']
        self.assertFalse(contacts.empty)
        # Each block has one contact of 100 m for A (on B) and for B (on C).
        self.assertAlmostEqual(self._length(contacts, 'A'), 200, delta=5)
        self.assertAlmostEqual(self._length(contacts, 'B'), 200, delta=5)
        self.assertAlmostEqual(call['kwargs']['bounding_box']['maxx'], 1100)

    def test_contacts_from_selected_features_only(self):
        # Select only the first block.
        self.geology.selectByExpression('x(centroid($geometry)) < 500')
        self.assertEqual(self.geology.selectedFeatureCount(), 3)
        call = self._run(QgsProcessingFeatureSourceDefinition(self.geology.id(), True))
        contacts = call['basal_contacts']
        self.assertFalse(contacts.empty)
        self.assertLessEqual(contacts.total_bounds[2], 100 + 1e-6)
        self.assertAlmostEqual(self._length(contacts, 'A'), 100, delta=5)
        self.assertAlmostEqual(self._length(contacts, 'B'), 100, delta=5)
        self.assertAlmostEqual(call['kwargs']['bounding_box']['maxx'], 100)


if __name__ == '__main__':
    unittest.main()
