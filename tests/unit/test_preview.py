"""Pytest tests for the map preview of a feature (grid, levels, isolines).

`loopstructural.main.preview` does not import QGIS, so the tests run in the
fast tests/unit/ job.
"""

import numpy as np
import pytest

pytest.importorskip('contourpy')

from loopstructural.main import preview


class TestGrid:
    def test_the_points_go_row_by_row(self):
        x, y, points = preview.grid_points([0, 10, -5], [4, 20, 5], 3)
        assert list(x) == [0, 2, 4]
        assert list(y) == [10, 15, 20]
        assert points.shape == (9, 3)
        assert list(points[:3, 1]) == [10, 10, 10]
        assert list(points[:3, 0]) == [0, 2, 4]

    def test_z_is_the_dem(self):
        _, _, points = preview.grid_points([0, 0], [1, 1], 2, lambda x, y: 100 + x + 2 * y)
        assert sorted(points[:, 2]) == [100, 101, 102, 103]

    def test_without_a_dem_z_is_zero(self):
        _, _, points = preview.grid_points([0, 0], [1, 1], 2)
        assert (points[:, 2] == 0).all()

    def test_a_grid_needs_two_points_on_each_side(self):
        with pytest.raises(ValueError):
            preview.grid_points([0, 0], [1, 1], 1)


class TestLevels:
    def test_the_levels_are_inside_the_range(self):
        levels = preview.default_levels([0.0, 10.0, np.nan], 4)
        assert len(levels) == 4
        assert levels.min() > 0 and levels.max() < 10
        assert np.allclose(np.diff(levels), np.diff(levels)[0])

    @pytest.mark.parametrize('values', [[], [np.nan], [5.0, 5.0]])
    def test_a_field_without_a_range_has_no_levels(self, values):
        assert len(preview.default_levels(values)) == 0


class TestIsolines:
    def setup_method(self):
        self.x = np.linspace(0, 10, 11)
        self.y = np.linspace(0, 10, 11)
        # a field that grows with X: the lines are straight and run along Y
        self.values = np.tile(self.x, (len(self.y), 1))

    def test_a_line_is_at_the_level(self):
        lines = preview.isolines(self.x, self.y, self.values, [2.5])
        assert len(lines) == 1
        level, coordinates = lines[0]
        assert level == 2.5
        assert np.allclose(coordinates[:, 0], 2.5)
        assert coordinates[:, 1].min() == 0 and coordinates[:, 1].max() == 10

    def test_a_level_outside_the_range_has_no_line(self):
        assert preview.isolines(self.x, self.y, self.values, [50.0]) == []

    def test_a_gap_stops_the_line(self):
        values = self.values.copy()
        values[:, 2:4] = np.nan
        assert preview.isolines(self.x, self.y, values, [2.5]) == []

    def test_the_shape_must_fit_the_grid(self):
        with pytest.raises(ValueError):
            preview.isolines(self.x, self.y, self.values.T[:, :5], [1.0])

    def test_the_points_of_the_grid_make_the_same_lines(self):
        x, y, points = preview.grid_points([0, 0], [10, 10], 11)
        values = points[:, 0].reshape(len(y), len(x))
        assert len(preview.isolines(x, y, values, preview.default_levels(values, 3))) == 3
