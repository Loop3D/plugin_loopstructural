#! python3

"""Test fault dip display in the Geological Features panel.

This module tests the logic for retrieving dip and pitch values from fault data,
which is used by FaultFeatureDetailsPanel.

Usage from the repo root folder:

.. code-block:: bash
    # for whole tests
    python -m unittest tests.qgis.test_fault_dip_display
    # for specific test
    python -m unittest tests.qgis.test_fault_dip_display.TestFaultDipRetrieval.test_dip_from_stored_data
"""

from qgis.testing import unittest
import pandas as pd
import numpy as np
from LoopStructural.utils import normal_vector_to_strike_and_dip

# Import the helper functions from the actual implementation
from loopstructural.gui.modelling.geological_model_tab.feature_details_panel import (
    retrieve_dip_value,
    retrieve_pitch_value,
)


class MockFault:
    """Simple fault mock for testing."""
    
    def __init__(self, name="TestFault", normal_vector=None):
        """Initialize mock fault."""
        self.name = name
        self.fault_normal_vector = normal_vector if normal_vector is not None else np.array([1.0, 0.0, 0.0])


class MockModelManager:
    """Simple model manager mock for testing."""
    
    def __init__(self):
        """Initialize mock manager."""
        self.faults = {}


class TestFaultDipRetrieval(unittest.TestCase):
    """Test dip and pitch value retrieval logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.fault = MockFault()
        self.model_manager = MockModelManager()

    def test_dip_from_stored_data(self):
        """Test that dip is retrieved from stored fault data when available."""
        # Create fault data with a dip of 45 degrees
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0],
            'dip': [45, 45, 45]
        })
        
        self.model_manager.faults['TestFault'] = {'data': fault_data}
        
        # Retrieve dip using the logic that FaultFeatureDetailsPanel uses
        dip = retrieve_dip_value(self.fault, self.model_manager)
        
        # Should get the average dip from stored data (45 degrees)
        self.assertEqual(dip, 45)

    def test_dip_fallback_to_normal_vector(self):
        """Test that dip falls back to normal vector calculation when not in stored data."""
        # No stored dip data
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0]
        })
        
        self.model_manager.faults['TestFault'] = {'data': fault_data}
        
        # Calculate expected dip from normal vector
        expected_dip = normal_vector_to_strike_and_dip(self.fault.fault_normal_vector)[0, 1]
        
        # Retrieve dip
        dip = retrieve_dip_value(self.fault, self.model_manager)
        
        # Should fall back to calculating from normal vector
        self.assertEqual(dip, expected_dip)

    def test_dip_default_when_no_data(self):
        """Test that dip falls back to normal vector when no fault data exists."""
        # No fault data at all
        self.model_manager.faults = {}
        
        # Retrieve dip
        dip = retrieve_dip_value(self.fault, self.model_manager)
        
        # Should calculate from normal vector
        self.assertIsInstance(dip, (int, float, np.floating))
        self.assertGreaterEqual(dip, 0)
        self.assertLessEqual(dip, 90)

    def test_dip_with_none_model_manager(self):
        """Test that dip falls back to normal vector when model_manager is None."""
        # Calculate expected dip from normal vector
        expected_dip = normal_vector_to_strike_and_dip(self.fault.fault_normal_vector)[0, 1]
        
        # Retrieve dip with None model manager
        dip = retrieve_dip_value(self.fault, None)
        
        # Should calculate from normal vector
        self.assertEqual(dip, expected_dip)

    def test_pitch_from_stored_data(self):
        """Test that pitch is retrieved from stored fault data when available."""
        # Create fault data with pitch
        fault_data = pd.DataFrame({
            'X': [0, 1, 2],
            'Y': [0, 1, 2],
            'Z': [0, 0, 0],
            'pitch': [30, 30, 30]
        })
        
        self.model_manager.faults['TestFault'] = {'data': fault_data}
        
        # Retrieve pitch
        pitch = retrieve_pitch_value(self.fault, self.model_manager)
        
        # Should get the average pitch from stored data
        self.assertEqual(pitch, 30)

    def test_pitch_default_when_no_data(self):
        """Test that pitch defaults to 0 when no fault data exists."""
        # No fault data at all
        self.model_manager.faults = {}
        
        # Retrieve pitch
        pitch = retrieve_pitch_value(self.fault, self.model_manager)
        
        # Should default to 0
        self.assertEqual(pitch, 0)

    def test_pitch_with_none_model_manager(self):
        """Test that pitch defaults to 0 when model_manager is None."""
        # Retrieve pitch with None model manager
        pitch = retrieve_pitch_value(self.fault, None)
        
        # Should default to 0
        self.assertEqual(pitch, 0)


if __name__ == "__main__":
    unittest.main()
