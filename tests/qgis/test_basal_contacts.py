import unittest
from pathlib import Path
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsVectorLayer,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsMessageLog,
    Qgis,
    QgsApplication,
)
from qgis.testing import start_app
from loopstructural.main.m2l_api import extract_basal_contacts
from loopstructural.processing.algorithms.extract_basal_contacts import BasalContactsAlgorithm
from loopstructural.processing.provider import Map2LoopProvider


class TestBasalContacts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.qgs = start_app()

        cls.provider = Map2LoopProvider()
        QgsApplication.processingRegistry().addProvider(cls.provider)

    def setUp(self):
        self.test_dir = Path(__file__).parent
        self.input_dir = self.test_dir / "input"

        self.geology_file = self.input_dir / "geol_clip_no_gaps.shp"
        self.faults_file = self.input_dir / "faults_clip.shp"
        self.strati_file = self.input_dir / "stratigraphic_column_testing.gpkg"

        self.assertTrue(self.geology_file.exists(), f"geology not found: {self.geology_file}")
        self.assertTrue(self.strati_file.exists(), f"strati not found: {self.strati_file}")
        if not self.faults_file.exists():
            QgsMessageLog.logMessage(
                f"faults not found: {self.faults_file}, will run test without faults",
                "TestBasalContacts",
                Qgis.Warning,
            )

    def test_basal_contacts_extraction(self):

        geology_layer = QgsVectorLayer(str(self.geology_file), "geology", "ogr")

        self.assertTrue(geology_layer.isValid(), "geology layer should be valid")
        self.assertGreater(geology_layer.featureCount(), 0, "geology layer should have features")

        faults_layer = None
        if self.faults_file.exists():
            faults_layer = QgsVectorLayer(str(self.faults_file), "faults", "ogr")
            self.assertTrue(faults_layer.isValid(), "faults layer should be valid")
            self.assertGreater(faults_layer.featureCount(), 0, "faults layer should have features")
            QgsMessageLog.logMessage(
                f"faults layer: {faults_layer.featureCount()} features",
                "TestBasalContacts",
                Qgis.Critical,
            )

        QgsMessageLog.logMessage(
            f"geology layer: {geology_layer.featureCount()} features",
            "TestBasalContacts",
            Qgis.Critical,
        )

        strati_table = QgsVectorLayer(str(self.strati_file), "strati", "ogr")
        algorithm = BasalContactsAlgorithm()
        algorithm.initAlgorithm()

        parameters = {
            'GEOLOGY': geology_layer,
            'UNIT_NAME_FIELD': 'unitname',
            'FORMATION_FIELD': 'formation',
            'FAULTS': faults_layer,
            'STRATIGRAPHIC_COLUMN': strati_table,
            'IGNORE_UNITS': [],
            'BASAL_CONTACTS': 'memory:basal_contacts',
            'ALL_CONTACTS': 'memory:all_contacts',
        }

        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()

        try:
            QgsMessageLog.logMessage(
                "Starting basal contacts algorithm...", "TestBasalContacts", Qgis.Critical
            )

            result = algorithm.processAlgorithm(parameters, context, feedback)

            QgsMessageLog.logMessage(f"Result: {result}", "TestBasalContacts", Qgis.Critical)

            self.assertIsNotNone(result, "result should not be None")
            self.assertIn('BASAL_CONTACTS', result, "Result should contain BASAL_CONTACTS key")
            self.assertIn('ALL_CONTACTS', result, "Result should contain ALL_CONTACTS key")

            basal_contacts_layer = context.takeResultLayer(result['BASAL_CONTACTS'])
            self.assertIsNotNone(basal_contacts_layer, "basal contacts layer should not be None")
            self.assertTrue(basal_contacts_layer.isValid(), "basal contacts layer should be valid")
            self.assertGreater(
                basal_contacts_layer.featureCount(), 0, "basal contacts layer should have features"
            )

            QgsMessageLog.logMessage(
                f"Generated {basal_contacts_layer.featureCount()} basal contacts",
                "TestBasalContacts",
                Qgis.Critical,
            )

            all_contacts_layer = context.takeResultLayer(result['ALL_CONTACTS'])
            self.assertIsNotNone(all_contacts_layer, "all contacts layer should not be None")
            self.assertTrue(all_contacts_layer.isValid(), "all contacts layer should be valid")
            self.assertGreater(
                all_contacts_layer.featureCount(), 0, "all contacts layer should have features"
            )

            QgsMessageLog.logMessage(
                f"Generated {all_contacts_layer.featureCount()} total contacts",
                "TestBasalContacts",
                Qgis.Critical,
            )

            QgsMessageLog.logMessage(
                "Basal contacts test completed successfully!", "TestBasalContacts", Qgis.Critical
            )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Basal contacts test error: {str(e)}", "TestBasalContacts", Qgis.Critical
            )
            QgsMessageLog.logMessage(
                f"Error type: {type(e).__name__}", "TestBasalContacts", Qgis.Critical
            )
            import traceback

            QgsMessageLog.logMessage(
                f"Full traceback:\n{traceback.format_exc()}", "TestBasalContacts", Qgis.Critical
            )
            raise

        finally:
            QgsMessageLog.logMessage("=" * 50, "TestBasalContacts", Qgis.Critical)

    @classmethod
    def tearDownClass(cls):
        try:
            registry = QgsApplication.processingRegistry()
            registry.removeProvider(cls.provider)
        except Exception:
            pass


class TestBasalContactOverrides(unittest.TestCase):
    """Units in basal_override_units get their full boundary as basal contact."""

    @classmethod
    def setUpClass(cls):
        cls.qgs = start_app()

    def _geology(self):
        # A, B and C are layers from top to bottom (0 <= x <= 100). D is
        # a unit on the right side (100 <= x <= 150) that touches all three.
        layer = QgsVectorLayer("Polygon?crs=EPSG:28350&field=unitname:string", "geology", "memory")
        polygons = {
            'A': "POLYGON((0 200, 100 200, 100 300, 0 300, 0 200))",
            'B': "POLYGON((0 100, 100 100, 100 200, 0 200, 0 100))",
            'C': "POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))",
            'D': "POLYGON((100 0, 150 0, 150 300, 100 300, 100 0))",
        }
        features = []
        for name, wkt in polygons.items():
            feature = QgsFeature(layer.fields())
            feature.setAttribute('unitname', name)
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        layer.dataProvider().addFeatures(features)
        return layer

    def _extract(self, order, overrides=None):
        return extract_basal_contacts(
            geology=self._geology(),
            stratigraphic_order=order,
            ignore_units=[],
            unit_name_field='unitname',
            basal_override_units=overrides,
        )['basal_contacts']

    def _length(self, contacts, unit):
        return contacts[contacts['basal_unit'] == unit].geometry.length.sum()

    def test_cover_not_in_column(self):
        contacts = self._extract(['A', 'B', 'C'])
        self.assertNotIn('D', set(contacts['basal_unit']))

        contacts = self._extract(['A', 'B', 'C'], overrides=['D'])
        self.assertAlmostEqual(self._length(contacts, 'D'), 300, delta=10)
        self.assertTrue((contacts[contacts['basal_unit'] == 'D']['type'] == 'BASAL').all())
        # the other units keep their basal contacts
        self.assertAlmostEqual(self._length(contacts, 'A'), 100, delta=5)
        self.assertAlmostEqual(self._length(contacts, 'B'), 100, delta=5)

    def test_intrusion_in_column(self):
        # without the override, the contact of D with the younger unit A
        # is given to A
        contacts = self._extract(['A', 'D', 'B', 'C'])
        self.assertLess(self._length(contacts, 'D'), 250)

        contacts = self._extract(['A', 'D', 'B', 'C'], overrides=['D'])
        self.assertAlmostEqual(self._length(contacts, 'D'), 300, delta=10)
        self.assertAlmostEqual(self._length(contacts, 'A'), 100, delta=5)


if __name__ == '__main__':
    unittest.main()
