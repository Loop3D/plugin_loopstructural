"""Pytest tests for `build_block_model_mesh` (see
loopstructural/gui/visualisation/cross_section_utils.py).

Only pyvista/numpy are needed, so these run in the fast tests/unit/ job.
"""

import numpy as np

from loopstructural.gui.visualisation.cross_section_utils import build_block_model_mesh


def test_block_model_fills_bounding_box():
    mesh = build_block_model_mesh((0, 10, -100), (100, 60, 0), (10, 5, 4))
    assert mesh.n_cells == 10 * 5 * 4
    np.testing.assert_allclose(mesh.bounds, (0, 100, 10, 60, -100, 0))


def test_block_model_cell_centres_are_inside_box():
    mesh = build_block_model_mesh((0, 0, 0), (10, 10, 10), (2, 2, 2))
    centres = mesh.cell_centers().points
    assert centres.shape == (8, 3)
    np.testing.assert_allclose(np.unique(centres[:, 0]), [2.5, 7.5])


def test_block_model_needs_at_least_one_cell_per_axis():
    mesh = build_block_model_mesh((0, 0, 0), (1, 1, 1), (0, 3, 3))
    assert mesh.n_cells == 1 * 3 * 3
