"""QGIS tests for grid export functionality.

This module tests grid export features that depend on the visualization
GUI components and PyQt5/QGIS.

Usage from the repo root folder:

.. code-block:: bash
    # for whole tests
    python -m unittest tests.qgis.test_grid_export
    # for specific test
    python -m unittest tests.qgis.test_grid_export.TestGridExport.test_export_grid_ascii_basic
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
from qgis.testing import unittest


class TestGridExport(unittest.TestCase):
    """Test grid export functionality."""

    def test_export_grid_ascii_basic(self):
        """Test ASCII export of a simple grid with scalar data."""
        # Create a mock mesh object that simulates a PyVista UniformGrid
        mock_mesh = MagicMock()
        mock_mesh.n_cells = 8
        
        # Mock cell centers
        mock_cell_centers = MagicMock()
        mock_cell_centers.points = np.array([
            [0.5, 0.5, 0.5],
            [1.5, 0.5, 0.5],
            [0.5, 1.5, 0.5],
            [1.5, 1.5, 0.5],
            [0.5, 0.5, 1.5],
            [1.5, 0.5, 1.5],
            [0.5, 1.5, 1.5],
            [1.5, 1.5, 1.5],
        ])
        mock_mesh.cell_centers.return_value = mock_cell_centers
        
        # Mock scalar data
        mock_mesh.active_scalars_name = "scalar_field"
        mock_mesh.cell_data = {
            "scalar_field": np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        }
        
        # Create a temporary file for export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            # Import the ObjectListWidget to get the export method
            from loopstructural.gui.visualisation.object_list_widget import ObjectListWidget
            
            # Create a minimal instance (viewer and properties_widget can be None for this test)
            widget = ObjectListWidget(viewer=MagicMock(), properties_widget=None)
            
            # Call the export method
            widget._export_grid_ascii(mock_mesh, temp_path, "test_grid")
            
            # Read the exported file
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            
            # Verify header
            self.assertEqual(lines[0].strip(), "# ASCII Grid Export: test_grid")
            self.assertEqual(lines[1].strip(), "# Format: x y z value")
            self.assertEqual(lines[2].strip(), "# Number of cells: 8")
            self.assertEqual(lines[3].strip(), "# Scalar field: scalar_field")
            self.assertEqual(lines[4].strip(), "#")
            
            # Verify data lines
            data_lines = lines[5:]
            self.assertEqual(len(data_lines), 8)
            
            # Verify first data line
            first_line = data_lines[0].strip().split()
            self.assertEqual(len(first_line), 4)
            self.assertAlmostEqual(float(first_line[0]), 0.5, places=5)
            self.assertAlmostEqual(float(first_line[1]), 0.5, places=5)
            self.assertAlmostEqual(float(first_line[2]), 0.5, places=5)
            self.assertAlmostEqual(float(first_line[3]), 1.0, places=5)
            
        finally:
            # Clean up
            Path(temp_path).unlink(missing_ok=True)

    def test_export_grid_ascii_no_scalars(self):
        """Test ASCII export when grid has no scalar data."""
        # Create a mock mesh without scalar data
        mock_mesh = MagicMock()
        mock_mesh.n_cells = 4
        
        mock_cell_centers = MagicMock()
        mock_cell_centers.points = np.array([
            [0.5, 0.5, 0.5],
            [1.5, 0.5, 0.5],
            [0.5, 1.5, 0.5],
            [1.5, 1.5, 0.5],
        ])
        mock_mesh.cell_centers.return_value = mock_cell_centers
        
        # No scalar data
        mock_mesh.active_scalars_name = None
        mock_mesh.cell_data = {}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            from loopstructural.gui.visualisation.object_list_widget import ObjectListWidget
            
            widget = ObjectListWidget(viewer=MagicMock(), properties_widget=None)
            widget._export_grid_ascii(mock_mesh, temp_path, "test_grid_no_scalars")
            
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            
            # Should still create file with zeros
            self.assertIn("# ASCII Grid Export: test_grid_no_scalars", lines[0])
            self.assertGreaterEqual(len(lines), 9)  # Header + 4 data lines
            
            # Verify that values are zero
            data_lines = lines[5:]
            for line in data_lines:
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) == 4:
                        value = float(parts[3])
                        self.assertAlmostEqual(value, 0.0, places=5)
            
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_mesh_type_detection(self):
        """Test that grid mesh types are correctly detected."""
        test_cases = [
            ("UniformGrid", True),
            ("ImageData", True),
            ("StructuredGrid", True),
            ("RectilinearGrid", True),
            ("PolyData", False),
            ("UnstructuredGrid", False),
        ]
        
        for mesh_type, expected_is_grid in test_cases:
            mock_mesh = MagicMock()
            mock_mesh.__class__.__name__ = mesh_type
            
            is_grid = type(mock_mesh).__name__ in ['UniformGrid', 'ImageData', 'StructuredGrid', 'RectilinearGrid']
            
            self.assertEqual(is_grid, expected_is_grid, f"Failed for mesh type: {mesh_type}")


if __name__ == "__main__":
    unittest.main()
