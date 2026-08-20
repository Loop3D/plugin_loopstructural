"""Pytest tests for the pure mesh/scalar/colormap helpers factored out of
ObjectPropertiesWidget (see loopstructural/gui/visualisation/mesh_scalar_utils.py).

None of these touch QGIS -- only numpy, matplotlib and vtk (all already
pulled in transitively via pyvista, a testing dependency) -- so unlike most
of this plugin's logic, they can run in the fast tests/unit/ job.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import vtk

from loopstructural.gui.visualisation.mesh_scalar_utils import (
    apply_colormap_lut,
    get_scalar_values,
    render_histogram,
)


class _FakeMesh:
    def __init__(self, point_data=None, cell_data=None):
        self.point_data = point_data or {}
        self.cell_data = cell_data or {}


class TestGetScalarValues:
    def test_none_mesh_returns_none(self):
        assert get_scalar_values(None, "foo") is None

    def test_none_or_placeholder_name_returns_none(self):
        mesh = _FakeMesh(point_data={"foo": [1, 2, 3]})
        assert get_scalar_values(mesh, None) is None
        assert get_scalar_values(mesh, "") is None
        assert get_scalar_values(mesh, "<none>") is None

    def test_point_data_lookup(self):
        mesh = _FakeMesh(point_data={"scalar_a": [1.0, 2.0, 3.0]})
        result = get_scalar_values(mesh, "scalar_a")
        assert list(result) == [1.0, 2.0, 3.0]

    def test_cell_data_lookup_with_prefix(self):
        mesh = _FakeMesh(cell_data={"scalar_b": [4.0, 5.0]})
        result = get_scalar_values(mesh, "cell:scalar_b")
        assert list(result) == [4.0, 5.0]

    def test_missing_array_returns_none(self):
        mesh = _FakeMesh(point_data={"scalar_a": [1.0]})
        assert get_scalar_values(mesh, "does_not_exist") is None

    def test_empty_array_returns_none(self):
        mesh = _FakeMesh(point_data={"scalar_a": []})
        assert get_scalar_values(mesh, "scalar_a") is None


class TestRenderHistogram:
    def setup_method(self):
        self.fig, self.ax = plt.subplots()

    def teardown_method(self):
        plt.close(self.fig)

    def test_none_values_draws_placeholder_text(self):
        render_histogram(self.ax, None)
        assert len(self.ax.texts) == 1
        assert self.ax.texts[0].get_text() == 'No scalar selected'
        assert len(self.ax.get_xticks()) == 0
        assert len(self.ax.get_yticks()) == 0

    def test_values_draws_histogram(self):
        values = np.array([1.0, 2.0, 2.0, 3.0, 3.0, 3.0])
        render_histogram(self.ax, values)
        assert len(self.ax.patches) > 0  # histogram bars were drawn
        assert self.ax.get_xlabel() == 'Value'
        assert self.ax.get_ylabel() == 'Count'

    def test_nan_values_are_dropped_before_histogramming(self):
        # a NaN in the auto-range would otherwise raise inside matplotlib
        values = np.array([1.0, 2.0, np.nan, 3.0, np.inf])
        render_histogram(self.ax, values)
        assert len(self.ax.patches) > 0
        assert self.ax.get_xlabel() == 'Value'

    def test_all_nan_values_draws_placeholder_text(self):
        values = np.array([np.nan, np.nan, np.inf])
        render_histogram(self.ax, values)
        assert len(self.ax.patches) == 0
        assert len(self.ax.texts) == 1
        assert self.ax.texts[0].get_text() == 'No finite scalar values'


class TestApplyColormapLut:
    def test_no_cmap_does_nothing(self):
        mapper = vtk.vtkPolyDataMapper()
        # should not raise
        apply_colormap_lut(mapper, None, None)

    def test_builds_and_assigns_lut(self):
        mapper = vtk.vtkPolyDataMapper()
        apply_colormap_lut(mapper, "viridis", clim=(0.0, 10.0))
        lut = mapper.GetLookupTable()
        assert lut is not None
        assert lut.GetNumberOfTableValues() == 256
        assert lut.GetRange() == (0.0, 10.0)

    def test_invalid_mapper_does_not_raise(self):
        class _NotAMapper:
            pass

        # no SetLookupTable/SetUseLookupTableScalarRange attrs -> should be a no-op, not raise
        apply_colormap_lut(_NotAMapper(), "viridis", None)

    def test_sets_nan_color(self):
        mapper = vtk.vtkPolyDataMapper()
        apply_colormap_lut(mapper, "viridis", clim=(0.0, 10.0), nan_color=(1.0, 0.0, 0.0, 1.0))
        lut = mapper.GetLookupTable()
        assert tuple(lut.GetNanColor()) == (1.0, 0.0, 0.0, 1.0)

    def test_nan_clim_is_ignored_instead_of_corrupting_range(self):
        mapper = vtk.vtkPolyDataMapper()
        # a caller that computed clim from an all-NaN array would land here
        apply_colormap_lut(mapper, "viridis", clim=(float('nan'), float('nan')))
        lut = mapper.GetLookupTable()
        # default vtkLookupTable range (0, 1), untouched by the NaN clim
        assert lut.GetRange() == (0.0, 1.0)
