"""Pytest tests for the threshold filter helpers in
loopstructural/gui/visualisation/mesh_scalar_utils.py.
"""

import numpy as np
import pytest
import pyvista as pv

from loopstructural.gui.visualisation.mesh_scalar_utils import (
    filter_array_names,
    threshold_mesh,
)


@pytest.fixture
def block_model():
    grid = pv.ImageData(dimensions=(5, 5, 5))
    grid.cell_data['stratigraphy'] = np.arange(grid.n_cells) % 4
    grid.cell_data['colour'] = np.zeros((grid.n_cells, 3), dtype=np.uint8)
    grid.point_data['z'] = grid.points[:, 2]
    return grid


def test_filter_array_names_lists_single_component_arrays(block_model):
    assert filter_array_names(block_model) == ['z', 'cell:stratigraphy']


def test_threshold_keeps_cells_in_range(block_model):
    result = threshold_mesh(block_model, {'scalars': 'cell:stratigraphy', 'min': 1, 'max': 2})
    assert set(np.unique(result.cell_data['stratigraphy'])) == {1, 2}


def test_threshold_invert_keeps_cells_outside_range(block_model):
    result = threshold_mesh(
        block_model, {'scalars': 'cell:stratigraphy', 'min': 1, 'max': 2, 'invert': True}
    )
    assert set(np.unique(result.cell_data['stratigraphy'])) == {0, 3}


def test_threshold_accepts_limits_in_either_order(block_model):
    result = threshold_mesh(block_model, {'scalars': 'cell:stratigraphy', 'min': 2, 'max': 1})
    assert set(np.unique(result.cell_data['stratigraphy'])) == {1, 2}


def test_threshold_on_point_array(block_model):
    result = threshold_mesh(block_model, {'scalars': 'z', 'min': 0, 'max': 2})
    assert result.n_cells > 0
    assert result.points[:, 2].max() <= 2


def test_threshold_missing_array_raises(block_model):
    with pytest.raises(KeyError):
        threshold_mesh(block_model, {'scalars': 'cell:missing', 'min': 0, 'max': 1})


def test_threshold_values_keeps_only_those_cells(block_model):
    result = threshold_mesh(block_model, {'scalars': 'cell:stratigraphy', 'values': [0, 3]})
    assert set(np.unique(result.cell_data['stratigraphy'])) == {0, 3}
    assert '_filter_mask' not in result.cell_data
    assert '_filter_mask' not in block_model.cell_data


def test_threshold_values_on_point_array_keeps_arrays():
    grid = pv.ImageData(dimensions=(5, 5, 5))
    grid.point_data['stratigraphy'] = (grid.points[:, 2] >= 2).astype(int)
    result = threshold_mesh(grid, {'scalars': 'stratigraphy', 'values': [1]})
    assert result.n_cells > 0
    assert set(np.unique(result.point_data['stratigraphy'])) == {1}
    assert '_filter_mask' not in grid.point_data


def test_threshold_no_values_gives_empty_mesh(block_model):
    result = threshold_mesh(block_model, {'scalars': 'cell:stratigraphy', 'values': []})
    assert result.n_cells == 0
