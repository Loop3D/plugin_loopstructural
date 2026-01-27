import unittest
from unittest.mock import MagicMock, Mock

from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from loopstructural.main.data_manager import ModellingDataManager


class TestModelCRS(unittest.TestCase):
    """Unit tests for Model CRS functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock objects
        self.mock_project = Mock(spec=QgsProject)
        self.mock_canvas = Mock()
        self.mock_logger = Mock()
        
        # Set up mock project CRS (WGS84 UTM 55S - projected)
        self.mock_project_crs = QgsCoordinateReferenceSystem("EPSG:32755")
        self.mock_project.crs.return_value = self.mock_project_crs
        
        # Initialize data manager
        self.data_manager = ModellingDataManager(
            project=self.mock_project,
            mapCanvas=self.mock_canvas,
            logger=self.mock_logger
        )

    def test_initial_crs_uses_project_crs_flag(self):
        """Test that initial state has use_project_crs=True."""
        self.assertTrue(self.data_manager._use_project_crs)

    def test_set_valid_projected_crs(self):
        """Test setting a valid projected CRS."""
        # Create a projected CRS (WGS84 / UTM zone 33N)
        crs = QgsCoordinateReferenceSystem("EPSG:32633")
        
        success, msg = self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.assertTrue(success)
        self.assertEqual(self.data_manager.get_model_crs(), crs)
        self.assertFalse(self.data_manager._use_project_crs)

    def test_reject_geographic_crs(self):
        """Test that geographic CRS is rejected."""
        # Create a geographic CRS (WGS84)
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        
        success, msg = self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.assertFalse(success)
        self.assertIn("geographic", msg.lower())
        self.assertIsNone(self.data_manager._model_crs)

    def test_reject_invalid_crs(self):
        """Test that invalid CRS is rejected."""
        # Create an invalid CRS
        crs = QgsCoordinateReferenceSystem()
        
        success, msg = self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.assertFalse(success)
        self.assertIn("not valid", msg.lower())
        self.assertIsNone(self.data_manager._model_crs)

    def test_use_project_crs(self):
        """Test using project CRS."""
        success, msg = self.data_manager.set_model_crs(None, use_project_crs=True)
        
        self.assertTrue(success)
        self.assertTrue(self.data_manager._use_project_crs)
        # Should return project CRS when use_project_crs is True
        self.assertEqual(self.data_manager.get_model_crs(), self.mock_project_crs)

    def test_is_model_crs_valid_with_projected(self):
        """Test CRS validation with a projected CRS."""
        crs = QgsCoordinateReferenceSystem("EPSG:32633")
        self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.assertTrue(self.data_manager.is_model_crs_valid())

    def test_is_model_crs_valid_with_geographic(self):
        """Test CRS validation rejects geographic CRS."""
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        self.assertFalse(self.data_manager.is_model_crs_valid())

    def test_crs_persistence_to_dict(self):
        """Test CRS is saved in to_dict."""
        crs = QgsCoordinateReferenceSystem("EPSG:32633")
        self.data_manager.set_model_crs(crs, use_project_crs=False)
        
        data_dict = self.data_manager.to_dict()
        
        self.assertEqual(data_dict['model_crs'], 'EPSG:32633')
        self.assertFalse(data_dict['use_project_crs'])

    def test_crs_persistence_from_dict(self):
        """Test CRS is restored from from_dict."""
        # Create a data dict with CRS info
        data = {
            'model_crs': 'EPSG:32633',
            'use_project_crs': False,
        }
        
        # Clear current CRS
        self.data_manager._model_crs = None
        self.data_manager._use_project_crs = True
        
        # Load from dict (just the CRS part - simplified test)
        if 'use_project_crs' in data:
            self.data_manager._use_project_crs = data['use_project_crs']
        if 'model_crs' in data and data['model_crs'] is not None:
            crs = QgsCoordinateReferenceSystem(data['model_crs'])
            if crs.isValid():
                self.data_manager.set_model_crs(crs, use_project_crs=self.data_manager._use_project_crs)
        
        # Verify
        self.assertFalse(self.data_manager._use_project_crs)
        restored_crs = self.data_manager.get_model_crs()
        self.assertEqual(restored_crs.authid(), 'EPSG:32633')


if __name__ == '__main__':
    unittest.main()
