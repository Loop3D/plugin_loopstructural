"""Test paint stratigraphic order algorithm."""

import unittest
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMessageLog,
    QgsPointXY,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant
from qgis.testing import start_app

from loopstructural.processing.algorithms.paint_stratigraphic_order import (
    PaintStratigraphicOrderAlgorithm,
)
from loopstructural.processing.provider import Map2LoopProvider


class TestPaintStratigraphicOrder(unittest.TestCase):
    """Tests for the Paint Stratigraphic Order algorithm."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        cls.qgs = start_app()

        cls.provider = Map2LoopProvider()
        QgsApplication.processingRegistry().addProvider(cls.provider)

    def setUp(self):
        """Set up test data."""
        self.test_dir = Path(__file__).parent
        self.input_dir = self.test_dir / "input"

        # Check if test data exists
        self.geology_file = self.input_dir / "geol_clip_no_gaps.shp"
        self.strati_file = self.input_dir / "stratigraphic_column_testing.gpkg"

    def test_paint_stratigraphic_order_with_test_data(self):
        """Test the algorithm with actual test data if available."""
        if not self.geology_file.exists() or not self.strati_file.exists():
            self.skipTest("Test data files not available")

        # Load geology layer
        geology_layer = QgsVectorLayer(str(self.geology_file), "geology", "ogr")
        self.assertTrue(geology_layer.isValid(), "geology layer should be valid")
        self.assertGreater(geology_layer.featureCount(), 0, "geology layer should have features")

        # Load stratigraphic column
        strati_layer = QgsVectorLayer(str(self.strati_file), "strati", "ogr")
        self.assertTrue(strati_layer.isValid(), "strati layer should be valid")
        self.assertGreater(strati_layer.featureCount(), 0, "strati layer should have features")

        # Initialize algorithm
        algorithm = PaintStratigraphicOrderAlgorithm()
        algorithm.initAlgorithm()

        # Set up parameters for stratigraphic order mode
        parameters = {
            'INPUT_POLYGONS': geology_layer,
            'UNIT_NAME_FIELD': 'unitname',
            'INPUT_STRAT_COLUMN': strati_layer,
            'STRAT_UNIT_NAME_FIELD': 'unit_name',
            'STRAT_THICKNESS_FIELD': '',
            'PAINT_MODE': 0,  # Stratigraphic Order
            'OUTPUT': 'memory:painted_order',
        }

        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()

        try:
            # Run algorithm
            result = algorithm.processAlgorithm(parameters, context, feedback)

            self.assertIsNotNone(result, "result should not be None")
            self.assertIn('OUTPUT', result, "Result should contain OUTPUT key")

            # Get output layer
            output_layer = context.takeResultLayer(result['OUTPUT'])
            self.assertIsNotNone(output_layer, "output layer should not be None")
            self.assertTrue(output_layer.isValid(), "output layer should be valid")
            self.assertGreater(output_layer.featureCount(), 0, "output layer should have features")

            # Check that the strat_order field was added
            field_names = [field.name() for field in output_layer.fields()]
            self.assertIn('strat_order', field_names, "output should have strat_order field")

            QgsMessageLog.logMessage(
                f"Generated {output_layer.featureCount()} features with stratigraphic order",
                "TestPaintStratigraphicOrder",
                Qgis.Critical,
            )

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Test error: {str(e)}", "TestPaintStratigraphicOrder", Qgis.Critical
            )
            import traceback

            QgsMessageLog.logMessage(
                f"Full traceback:\n{traceback.format_exc()}",
                "TestPaintStratigraphicOrder",
                Qgis.Critical,
            )
            raise

    def test_paint_stratigraphic_order_synthetic(self):
        """Test the algorithm with synthetic data."""
        # Create a synthetic stratigraphic column layer
        strat_fields = QgsFields()
        strat_fields.append(QgsField("unit_name", QVariant.String))
        strat_fields.append(QgsField("thickness", QVariant.Double))

        strat_layer = QgsVectorLayer("None", "strat_column", "memory")
        strat_layer.dataProvider().addAttributes(strat_fields)
        strat_layer.updateFields()

        # Add stratigraphic units (youngest to oldest)
        units = [
            ("Unit_A", 100.0),
            ("Unit_B", 200.0),
            ("Unit_C", 150.0),
        ]

        for unit_name, thickness in units:
            feat = QgsFeature(strat_fields)
            feat.setAttributes([unit_name, thickness])
            strat_layer.dataProvider().addFeature(feat)

        strat_layer.updateExtents()
        self.assertEqual(strat_layer.featureCount(), 3, "strat layer should have 3 features")

        # Create a synthetic geology polygon layer
        geol_fields = QgsFields()
        geol_fields.append(QgsField("UNITNAME", QVariant.String))

        geol_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "geology", "memory")
        geol_layer.dataProvider().addAttributes(geol_fields)
        geol_layer.updateFields()

        # Add polygons for each unit
        polygon_units = ["Unit_A", "Unit_B", "Unit_C", "Unknown_Unit"]
        for i, unit_name in enumerate(polygon_units):
            feat = QgsFeature(geol_fields)
            # Create a simple square polygon
            x = i * 2
            points = [
                QgsPointXY(x, 0),
                QgsPointXY(x + 1, 0),
                QgsPointXY(x + 1, 1),
                QgsPointXY(x, 1),
                QgsPointXY(x, 0),
            ]
            feat.setGeometry(QgsGeometry.fromPolygonXY([points]))
            feat.setAttributes([unit_name])
            geol_layer.dataProvider().addFeature(feat)

        geol_layer.updateExtents()
        self.assertEqual(geol_layer.featureCount(), 4, "geol layer should have 4 features")

        # Test stratigraphic order mode
        algorithm = PaintStratigraphicOrderAlgorithm()
        algorithm.initAlgorithm()

        parameters = {
            'INPUT_POLYGONS': geol_layer,
            'UNIT_NAME_FIELD': 'UNITNAME',
            'INPUT_STRAT_COLUMN': strat_layer,
            'STRAT_UNIT_NAME_FIELD': 'unit_name',
            'STRAT_THICKNESS_FIELD': 'thickness',
            'PAINT_MODE': 0,  # Stratigraphic Order
            'OUTPUT': 'memory:painted_order',
        }

        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()

        result = algorithm.processAlgorithm(parameters, context, feedback)

        # Get output layer
        output_layer = context.takeResultLayer(result['OUTPUT'])
        self.assertIsNotNone(output_layer, "output layer should not be None")
        self.assertTrue(output_layer.isValid(), "output layer should be valid")
        self.assertEqual(output_layer.featureCount(), 4, "output should have 4 features")

        # Check strat_order values
        features = list(output_layer.getFeatures())
        
        # Unit_A should have order 0 (youngest)
        unit_a_feat = next((f for f in features if f['UNITNAME'] == 'Unit_A'), None)
        self.assertIsNotNone(unit_a_feat, "Unit_A feature should exist")
        self.assertEqual(unit_a_feat['strat_order'], 0, "Unit_A should have order 0")

        # Unit_B should have order 1
        unit_b_feat = next((f for f in features if f['UNITNAME'] == 'Unit_B'), None)
        self.assertIsNotNone(unit_b_feat, "Unit_B feature should exist")
        self.assertEqual(unit_b_feat['strat_order'], 1, "Unit_B should have order 1")

        # Unit_C should have order 2 (oldest)
        unit_c_feat = next((f for f in features if f['UNITNAME'] == 'Unit_C'), None)
        self.assertIsNotNone(unit_c_feat, "Unit_C feature should exist")
        self.assertEqual(unit_c_feat['strat_order'], 2, "Unit_C should have order 2")

        # Unknown_Unit should have None
        unknown_feat = next((f for f in features if f['UNITNAME'] == 'Unknown_Unit'), None)
        self.assertIsNotNone(unknown_feat, "Unknown_Unit feature should exist")
        self.assertIsNone(unknown_feat['strat_order'], "Unknown_Unit should have None order")

    def test_paint_cumulative_thickness(self):
        """Test the algorithm with cumulative thickness mode."""
        # Create a synthetic stratigraphic column layer
        strat_fields = QgsFields()
        strat_fields.append(QgsField("unit_name", QVariant.String))
        strat_fields.append(QgsField("thickness", QVariant.Double))

        strat_layer = QgsVectorLayer("None", "strat_column", "memory")
        strat_layer.dataProvider().addAttributes(strat_fields)
        strat_layer.updateFields()

        # Add stratigraphic units (youngest to oldest)
        units = [
            ("Unit_A", 100.0),
            ("Unit_B", 200.0),
            ("Unit_C", 150.0),
        ]

        for unit_name, thickness in units:
            feat = QgsFeature(strat_fields)
            feat.setAttributes([unit_name, thickness])
            strat_layer.dataProvider().addFeature(feat)

        strat_layer.updateExtents()

        # Create a synthetic geology polygon layer
        geol_fields = QgsFields()
        geol_fields.append(QgsField("UNITNAME", QVariant.String))

        geol_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "geology", "memory")
        geol_layer.dataProvider().addAttributes(geol_fields)
        geol_layer.updateFields()

        # Add polygons for each unit
        polygon_units = ["Unit_A", "Unit_B", "Unit_C"]
        for i, unit_name in enumerate(polygon_units):
            feat = QgsFeature(geol_fields)
            # Create a simple square polygon
            x = i * 2
            points = [
                QgsPointXY(x, 0),
                QgsPointXY(x + 1, 0),
                QgsPointXY(x + 1, 1),
                QgsPointXY(x, 1),
                QgsPointXY(x, 0),
            ]
            feat.setGeometry(QgsGeometry.fromPolygonXY([points]))
            feat.setAttributes([unit_name])
            geol_layer.dataProvider().addFeature(feat)

        geol_layer.updateExtents()

        # Test cumulative thickness mode
        algorithm = PaintStratigraphicOrderAlgorithm()
        algorithm.initAlgorithm()

        parameters = {
            'INPUT_POLYGONS': geol_layer,
            'UNIT_NAME_FIELD': 'UNITNAME',
            'INPUT_STRAT_COLUMN': strat_layer,
            'STRAT_UNIT_NAME_FIELD': 'unit_name',
            'STRAT_THICKNESS_FIELD': 'thickness',
            'PAINT_MODE': 1,  # Cumulative Thickness
            'OUTPUT': 'memory:painted_thickness',
        }

        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()

        result = algorithm.processAlgorithm(parameters, context, feedback)

        # Get output layer
        output_layer = context.takeResultLayer(result['OUTPUT'])
        self.assertIsNotNone(output_layer, "output layer should not be None")
        self.assertTrue(output_layer.isValid(), "output layer should be valid")

        # Check cum_thickness values
        features = list(output_layer.getFeatures())
        
        # Unit_C (oldest) should have cumulative thickness 0
        unit_c_feat = next((f for f in features if f['UNITNAME'] == 'Unit_C'), None)
        self.assertIsNotNone(unit_c_feat, "Unit_C feature should exist")
        self.assertEqual(unit_c_feat['cum_thickness'], 0.0, "Unit_C should have cum_thickness 0")

        # Unit_B should have cumulative thickness 150 (thickness of Unit_C)
        unit_b_feat = next((f for f in features if f['UNITNAME'] == 'Unit_B'), None)
        self.assertIsNotNone(unit_b_feat, "Unit_B feature should exist")
        self.assertEqual(unit_b_feat['cum_thickness'], 150.0, "Unit_B should have cum_thickness 150")

        # Unit_A (youngest) should have cumulative thickness 350 (150 + 200)
        unit_a_feat = next((f for f in features if f['UNITNAME'] == 'Unit_A'), None)
        self.assertIsNotNone(unit_a_feat, "Unit_A feature should exist")
        self.assertEqual(
            unit_a_feat['cum_thickness'], 350.0, "Unit_A should have cum_thickness 350"
        )

    @classmethod
    def tearDownClass(cls):
        """Clean up after tests."""
        try:
            registry = QgsApplication.processingRegistry()
            registry.removeProvider(cls.provider)
        except Exception:
            pass


if __name__ == '__main__':
    unittest.main()
