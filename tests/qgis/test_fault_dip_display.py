#! python3

"""Test fault dip display in the Geological Features panel.

Usage from the repo root folder:

.. code-block:: bash
    # for whole tests
    python -m pytest tests/qgis/test_fault_dip_display.py
    # for specific test
    python -m pytest tests/qgis/test_fault_dip_display.py::test_dip_from_stored_data
"""

import unittest
from unittest.mock import MagicMock, Mock
import pandas as pd
import numpy as np


class TestFaultDipDisplay(unittest.TestCase):
    """Test fault dip retrieval and display."""

    def setUp(self):
        """Set up mock objects for testing."""
        # Mock the fault object
        self.mock_fault = Mock()
        self.mock_fault.name = "TestFault"
        self.mock_fault.displacement = 100
        self.mock_fault.fault_major_axis = 500
        self.mock_fault.fault_minor_axis = 300
        self.mock_fault.fault_intermediate_axis = 400
        
        # Mock fault_normal_vector that would give a dip of 90 (vertical fault)
        self.mock_fault.fault_normal_vector = np.array([1.0, 0.0, 0.0])
        
        # Mock the model manager
        self.mock_model_manager = Mock()
        self.mock_model_manager.faults = {}

    def test_dip_from_stored_data(self):
        """Test that dip is retrieved from stored fault data when available."""
        # Create fault data with a dip of 45 degrees
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0],
            'dip': [45, 45, 45]
        })
        
        self.mock_model_manager.faults['TestFault'] = {'data': fault_data}
        
        from loopstructural.gui.modelling.geological_model_tab.feature_details_panel import (
            FaultFeatureDetailsPanel
        )
        
        # Create the panel - this should retrieve dip from stored data
        panel = FaultFeatureDetailsPanel(
            parent=None,
            fault=self.mock_fault,
            model_manager=self.mock_model_manager,
            data_manager=None
        )
        
        # Check that the dip was retrieved from stored data (45 degrees)
        # not from the normal vector calculation (which would be 90 degrees)
        self.assertEqual(panel.fault_parameters['dip'], 45)

    def test_dip_fallback_to_normal_vector(self):
        """Test that dip falls back to normal vector calculation when not in stored data."""
        # No stored dip data
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0]
        })
        
        self.mock_model_manager.faults['TestFault'] = {'data': fault_data}
        
        from loopstructural.gui.modelling.geological_model_tab.feature_details_panel import (
            FaultFeatureDetailsPanel
        )
        from LoopStructural.utils import normal_vector_to_strike_and_dip
        
        # Calculate expected dip from normal vector
        expected_dip = normal_vector_to_strike_and_dip(self.mock_fault.fault_normal_vector)[0, 1]
        
        panel = FaultFeatureDetailsPanel(
            parent=None,
            fault=self.mock_fault,
            model_manager=self.mock_model_manager,
            data_manager=None
        )
        
        # Should fall back to calculating from normal vector
        self.assertEqual(panel.fault_parameters['dip'], expected_dip)

    def test_dip_default_when_no_data(self):
        """Test that dip defaults to 90 when no fault data exists."""
        # No fault data at all
        self.mock_model_manager.faults = {}
        
        from loopstructural.gui.modelling.geological_model_tab.feature_details_panel import (
            FaultFeatureDetailsPanel
        )
        
        panel = FaultFeatureDetailsPanel(
            parent=None,
            fault=self.mock_fault,
            model_manager=self.mock_model_manager,
            data_manager=None
        )
        
        # Should use a reasonable default or calculate from normal vector
        self.assertIsInstance(panel.fault_parameters['dip'], (int, float))
        self.assertGreaterEqual(panel.fault_parameters['dip'], 0)
        self.assertLessEqual(panel.fault_parameters['dip'], 90)

    def test_pitch_from_stored_data(self):
        """Test that pitch is also retrieved from stored fault data when available."""
        # Create fault data with pitch
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0],
            'dip': [45, 45, 45],
            'pitch': [30, 30, 30]
        })
        
        self.mock_model_manager.faults['TestFault'] = {'data': fault_data}
        
        from loopstructural.gui.modelling.geological_model_tab.feature_details_panel import (
            FaultFeatureDetailsPanel
        )
        
        panel = FaultFeatureDetailsPanel(
            parent=None,
            fault=self.mock_fault,
            model_manager=self.mock_model_manager,
            data_manager=None
        )
        
        # Check that pitch was retrieved from stored data
        self.assertEqual(panel.fault_parameters['pitch'], 30)


if __name__ == "__main__":
    unittest.main()
