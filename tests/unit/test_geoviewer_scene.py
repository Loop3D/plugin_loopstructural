"""Tests for the objects that a model gives to GeoViewer (main/geoviewer/scene.py)."""

from types import SimpleNamespace

import pyvista as pv
import pytest

from loopstructural.main.geoviewer import protocol, scene
from loopstructural.main.geoviewer.link import SkippedObject


class FakeSurface:
    def __init__(self, name, mesh=None):
        self.name = name
        self._mesh = mesh if mesh is not None else pv.Sphere(radius=1.0, center=(1000, 2000, -10))

    def vtk(self):
        return self._mesh


class FakeModel:
    def __init__(self, strat=(), faults=()):
        self.bounding_box = SimpleNamespace(origin=(0, 0, -100), maximum=(2001, 4001, 0))
        self._strat, self._faults = list(strat), list(faults)

    def get_stratigraphic_surfaces(self):
        return self._strat

    def get_fault_surfaces(self):
        return self._faults


def headers(messages):
    return [(object_id, protocol.decode_header(frame)) for object_id, frame in messages]


def test_origin_is_the_rounded_centre_with_zero_z():
    assert scene.proposed_origin(FakeModel()) == [1000.0, 2000.0, 0.0]


def test_groups_come_before_the_surfaces():
    manager = SimpleNamespace(model=FakeModel([FakeSurface('a')], [FakeSurface('f')]))
    result = headers(scene.model_messages(manager, (0, 0, 0), revision=7))
    ids = [object_id for object_id, _ in result]
    assert ids == [
        'loopstructural/model',
        'loopstructural/model/stratigraphy',
        'loopstructural/model/faults',
        'loopstructural/model/stratigraphy/a',
        'loopstructural/model/faults/f',
    ]
    by_id = dict(result)
    assert by_id['loopstructural/model/faults/f']['parent'] == 'loopstructural/model/faults'
    assert by_id['loopstructural/model/faults/f']['style']['colour'] == scene.FAULT_COLOUR
    assert by_id['loopstructural/model/stratigraphy/a']['style'] == {}
    assert all(h['revision'] == 7 for h in by_id.values())
    assert all(object_id.startswith(scene.ID_PREFIX) for object_id in ids)


def test_only_the_selected_kinds_are_sent():
    manager = SimpleNamespace(model=FakeModel([FakeSurface('a')], [FakeSurface('f')]))
    ids = [i for i, _ in scene.model_messages(manager, (0, 0, 0), faults=False)]
    assert 'loopstructural/model/faults' not in ids and 'loopstructural/model/stratigraphy/a' in ids


def test_same_name_gets_a_suffix():
    manager = SimpleNamespace(model=FakeModel([FakeSurface('a'), FakeSurface('a')]))
    ids = [i for i, _ in scene.model_messages(manager, (0, 0, 0))]
    assert ids[-2:] == [
        'loopstructural/model/stratigraphy/a',
        'loopstructural/model/stratigraphy/a_2',
    ]


def test_empty_surface_is_skipped_and_all_empty_is_an_error():
    manager = SimpleNamespace(model=FakeModel([FakeSurface('a'), FakeSurface('b', pv.PolyData())]))
    ids = [i for i, _ in scene.model_messages(manager, (0, 0, 0))]
    assert 'loopstructural/model/stratigraphy/b' not in ids
    manager = SimpleNamespace(model=FakeModel([FakeSurface('b', pv.PolyData())]))
    with pytest.raises(scene.PushError, match='empty'):
        list(scene.model_messages(manager, (0, 0, 0)))


def test_no_model_and_no_surfaces_are_errors():
    with pytest.raises(scene.PushError, match='Build the model'):
        list(scene.model_messages(SimpleNamespace(model=None), (0, 0, 0)))
    with pytest.raises(scene.PushError, match='no surfaces'):
        list(scene.model_messages(SimpleNamespace(model=FakeModel()), (0, 0, 0)))


def test_triangles_of_a_quad_mesh_are_triangulated():
    quad = pv.PolyData([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], faces=[4, 0, 1, 2, 3])
    vertices, triangles = scene.triangles_of(quad)
    assert triangles.shape == (2, 3) and triangles.max() < len(vertices)


class BrokenSurface(FakeSurface):
    def vtk(self):
        raise ValueError('no mesh')


def test_a_bad_surface_is_skipped_and_the_push_continues():
    manager = SimpleNamespace(model=FakeModel([BrokenSurface('bad'), FakeSurface('a')]))
    messages = list(scene.model_messages(manager, (0, 0, 0)))
    by_id = dict(messages)
    assert isinstance(by_id['loopstructural/model/stratigraphy/bad'], SkippedObject)
    assert 'no mesh' in by_id['loopstructural/model/stratigraphy/bad'].reason
    assert protocol.decode_header(by_id['loopstructural/model/stratigraphy/a'])['type']


def test_only_bad_surfaces_is_an_error():
    manager = SimpleNamespace(model=FakeModel([BrokenSurface('bad')]))
    with pytest.raises(scene.PushError, match='no mesh'):
        list(scene.model_messages(manager, (0, 0, 0)))
