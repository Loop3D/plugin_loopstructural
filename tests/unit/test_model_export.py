"""Pytest tests for `main.model_export`.

A fake model manager gives surfaces and a stratigraphy, so only pyvista and
numpy are needed.
"""

from types import SimpleNamespace

import numpy as np
import pyvista as pv
import pytest

from loopstructural.main import model_export


class FakeSurface:
    def __init__(self, name, empty=False):
        self.name = name
        self._empty = empty

    def vtk(self):
        return pv.PolyData() if self._empty else pv.Sphere(radius=1.0)


class FakeModel:
    def __init__(self, strat=(), faults=()):
        self.bounding_box = SimpleNamespace(origin=(0, 0, 0), maximum=(10, 10, 10))
        self._strat, self._faults = list(strat), list(faults)

    def get_stratigraphic_surfaces(self):
        return self._strat

    def get_fault_surfaces(self):
        return self._faults


class FakeManager:
    def __init__(self, model):
        self.model = model

    def evaluate_stratigraphy_on_points(self, points):
        # unit 0 below z = 5, unit 1 above
        return (np.asarray(points)[:, 2] > 5).astype(int)

    def get_stratigraphic_unit_names(self):
        return ['lower', 'upper']


def test_safe_file_name_and_unique_names():
    assert model_export.safe_file_name('a b/c') == 'a_b_c'
    assert model_export.safe_file_name('///') == 'surface'
    assert model_export.unique_names(['a b', 'a_b', 'a_b']) == ['a_b', 'a_b_2', 'a_b_3']


def test_export_surfaces_writes_one_file_each_and_skips_empty(tmp_path):
    model = FakeModel(
        strat=[FakeSurface('unit a'), FakeSurface('top', empty=True)], faults=[FakeSurface('F1')]
    )
    files = model_export.export_surfaces(FakeManager(model), tmp_path / 'out', '.vtk')
    assert sorted(f.name for f in files) == ['fault_F1.vtk', 'strat_unit_a.vtk']
    assert all(f.exists() for f in files)


def test_export_surfaces_can_select_kinds(tmp_path):
    model = FakeModel(strat=[FakeSurface('a')], faults=[FakeSurface('F1')])
    files = model_export.export_surfaces(
        FakeManager(model), tmp_path, '.vtp', stratigraphic=False
    )
    assert [f.name for f in files] == ['fault_F1.vtp']


def test_export_surfaces_errors(tmp_path):
    with pytest.raises(model_export.ExportError):
        model_export.export_surfaces(FakeManager(FakeModel()), tmp_path)
    with pytest.raises(model_export.ExportError):
        model_export.export_surfaces(FakeManager(None), tmp_path)
    with pytest.raises(model_export.ExportError):
        model_export.export_surfaces(
            FakeManager(FakeModel(strat=[FakeSurface('a', empty=True)])), tmp_path
        )
    with pytest.raises(model_export.ExportError):
        model_export.export_surfaces(FakeManager(FakeModel(strat=[FakeSurface('a')])), tmp_path, '.xyz')


def test_export_block_model_vtk_has_stratigraphy(tmp_path):
    path = model_export.export_block_model(
        FakeManager(FakeModel()), tmp_path / 'block.vtk', (2, 2, 2)
    )
    mesh = pv.read(str(path))
    assert mesh.n_cells == 8
    assert sorted(set(mesh.cell_data[model_export.STRATIGRAPHY_ID_FIELD])) == [0, 1]


def test_export_block_model_csv(tmp_path):
    path = model_export.export_block_model(
        FakeManager(FakeModel()), tmp_path / 'block.csv', (1, 1, 2)
    )
    lines = path.read_text(encoding='utf-8').splitlines()
    assert lines[0] == 'x,y,z,stratigraphy_id,unit'
    assert lines[1].endswith('0,"lower"')
    assert lines[2].endswith('1,"upper"')


def test_export_cross_section_plane_and_line(tmp_path):
    manager = FakeManager(FakeModel())
    plane = model_export.export_cross_section(
        manager, tmp_path / 'plane.vtk', origin=(5, 5, 5), normal=(0, 1, 0), size=10, resolution=5
    )
    assert pv.read(str(plane)).n_cells == 25
    line = model_export.export_cross_section(
        manager, tmp_path / 'line.csv', line_xy=[(0, 0), (10, 10)], resolution=4, z_resolution=3
    )
    assert len(line.read_text(encoding='utf-8').splitlines()) == 1 + 4 * 3


def test_export_cross_section_needs_input(tmp_path):
    manager = FakeManager(FakeModel())
    with pytest.raises(model_export.ExportError):
        model_export.export_cross_section(manager, tmp_path / 'x.vtk')
    with pytest.raises(model_export.ExportError):
        model_export.export_cross_section(
            manager, tmp_path / 'x.vtk', origin=(0, 0, 0), normal=(0, 0, 0), size=1
        )
