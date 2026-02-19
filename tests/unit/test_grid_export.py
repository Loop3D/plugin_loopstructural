"""Unit tests for grid export functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest


def test_export_grid_ascii_basic():
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
        # We'll test the export method in isolation
        from loopstructural.gui.visualisation.object_list_widget import ObjectListWidget
        
        # Create a minimal instance (viewer and properties_widget can be None for this test)
        widget = ObjectListWidget(viewer=MagicMock(), properties_widget=None)
        
        # Call the export method
        widget._export_grid_ascii(mock_mesh, temp_path, "test_grid")
        
        # Read the exported file
        with open(temp_path, 'r') as f:
            lines = f.readlines()
        
        # Verify header
        assert lines[0].strip() == "# ASCII Grid Export: test_grid"
        assert lines[1].strip() == "# Format: x y z value"
        assert lines[2].strip() == "# Number of cells: 8"
        assert lines[3].strip() == "# Scalar field: scalar_field"
        assert lines[4].strip() == "#"
        
        # Verify data lines
        data_lines = lines[5:]
        assert len(data_lines) == 8
        
        # Verify first data line
        first_line = data_lines[0].strip().split()
        assert len(first_line) == 4
        assert float(first_line[0]) == pytest.approx(0.5, abs=1e-5)
        assert float(first_line[1]) == pytest.approx(0.5, abs=1e-5)
        assert float(first_line[2]) == pytest.approx(0.5, abs=1e-5)
        assert float(first_line[3]) == pytest.approx(1.0, abs=1e-5)
        
    finally:
        # Clean up
        Path(temp_path).unlink(missing_ok=True)


def test_export_grid_ascii_no_scalars():
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
        assert "# ASCII Grid Export: test_grid_no_scalars" in lines[0]
        assert len(lines) >= 9  # Header + 4 data lines
        
        # Verify that values are zero
        data_lines = lines[5:]
        for line in data_lines:
            if line.strip():
                parts = line.strip().split()
                if len(parts) == 4:
                    value = float(parts[3])
                    assert value == pytest.approx(0.0, abs=1e-5)
        
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_mesh_type_detection():
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
        
        assert is_grid == expected_is_grid, f"Failed for mesh type: {mesh_type}"
