"""Tests for the mesh builders of the viewer (see
loopstructural/gui/visualisation/mesh_builders.py), with a stand-in model."""

from unittest.mock import Mock

import pyvista as pv
import pytest

from loopstructural.gui.visualisation.mesh_builders import MeshBuilder


class FakeSurface:
    def __init__(self, mesh):
        self._mesh = mesh

    def vtk(self):
        return self._mesh


class FakeFeature:
    """A feature whose surface exists only for values from 0 to 1."""

    def __init__(self):
        self.calls = []

    def surfaces(self, value=None):
        self.calls.append(value)
        if value is None or 0.0 <= value <= 1.0:
            return [FakeSurface(pv.Sphere())]
        return []

    def min(self):
        return 0.0

    def max(self):
        return 1.0


@pytest.fixture
def builder():
    model = Mock()
    model.__getitem__ = Mock(side_effect=lambda name: feature)
    model.get_feature_by_name = Mock(return_value=object())
    feature = FakeFeature()
    manager = Mock()
    manager.model = model
    result = MeshBuilder(manager)
    result.feature = feature
    return result


def test_isosurface_is_built_at_the_value(builder):
    mesh = builder.isosurface('f', 0.5)
    assert mesh.n_points > 0
    assert builder.feature.calls == [0.5]


def test_isosurface_outside_the_field_raises(builder):
    with pytest.raises(ValueError):
        builder.isosurface('f', 5.0)


def test_scalar_range(builder):
    assert builder.scalar_range('f') == (0.0, 1.0)


def test_rebuild_an_isosurface_uses_its_value(builder):
    spec = {
        'name': 'f_iso_0.25',
        'source_type': 'feature_isosurface',
        'source_feature': 'f',
        'isovalue': 0.25,
        'metadata': {},
    }
    mesh, overrides = builder.rebuild(spec)
    assert mesh.n_points > 0 and overrides == {}
    assert builder.feature.calls == [0.25]


def test_rebuild_an_isosurface_without_a_value_raises(builder):
    spec = {
        'name': 'x',
        'source_type': 'feature_isosurface',
        'source_feature': 'f',
        'isovalue': None,
        'metadata': {},
    }
    with pytest.raises(ValueError):
        builder.rebuild(spec)


def test_rebuild_an_unknown_type_raises(builder):
    spec = {
        'name': 'x',
        'source_type': 'other',
        'source_feature': None,
        'isovalue': None,
        'metadata': {},
    }
    with pytest.raises(ValueError):
        builder.rebuild(spec)
