"""Tests for the objects that a model gives to loop_link (main/geoviewer/scene.py)."""

from types import SimpleNamespace

import numpy as np
import pytest
import pyvista as pv

pytest.importorskip('loop_link')

from loop_link import BlockModel, Categorical, Lines, Points, Surface, Vectors

from loopstructural.main.geoviewer import scene
from loopstructural.main.geoviewer.scene import Group, Item, Skipped

ORIGIN = (0.0, 0.0, -100.0)
MAXIMUM = (2000.0, 4000.0, 0.0)


class FakeSurface:
    def __init__(self, name, mesh=None, colour=None):
        self.name = name
        self.colour = colour
        self._mesh = mesh if mesh is not None else pv.Sphere(radius=1.0, center=(1000, 2000, -10))

    def vtk(self):
        return self._mesh


class FakeFeature:
    def __init__(self, name, data=(), field=None):
        self.name = name
        self._data = list(data)
        self._field = field

    def get_data(self):
        return self._data

    def vector_field(self):
        if self._field is None:
            raise ValueError("no gradient")
        return self._field


class FakeModel:
    def __init__(self, strat=(), faults=(), features=()):
        self.bounding_box = SimpleNamespace(origin=ORIGIN, maximum=MAXIMUM)
        self._strat, self._faults = list(strat), list(faults)
        self.features = list(features)

    def __getitem__(self, name):
        return next(f for f in self.features if f.name == name)

    def get_stratigraphic_surfaces(self):
        return self._strat

    def get_fault_surfaces(self):
        return self._faults

    def evaluate_feature_value(self, name, points):
        if name == 'bad':
            raise RuntimeError("cannot evaluate")
        return np.asarray(points)[:, 2]

    def rescale(self, points):
        return np.asarray(points)


class FakeManager:
    def __init__(self, model, units=('young', 'old'), dem=None):
        self.model = model
        self._units = list(units)
        self._dem = dem

    def get_stratigraphic_unit_names(self):
        return self._units

    def get_stratigraphic_column_colours(self):
        return ['#ff0000', '#00ff00'][: len(self._units)]

    def evaluate_stratigraphy_on_points(self, points):
        z = np.asarray(points)[:, 2]
        return np.where(z > -50, 0, np.where(z > -90, 1, -1))

    def sample_dem_grid(self, resolution=100):
        x = np.linspace(ORIGIN[0], MAXIMUM[0], resolution)
        y = np.linspace(ORIGIN[1], MAXIMUM[1], resolution)
        xx, yy = np.meshgrid(x, y)
        zz = self._dem(xx, yy) if self._dem is not None else np.full_like(xx, -5.0)
        return xx, yy, zz


def by_id(values):
    return {v.id: v for v in values if not isinstance(v, Group)}


def make(manager, kinds, **options):
    return list(scene.model_items(manager, kinds, **options))


def test_origin_is_the_rounded_centre_with_zero_z():
    assert scene.proposed_origin(FakeModel()) == [1000.0, 2000.0, 0.0]


def test_groups_come_before_their_objects():
    manager = FakeManager(FakeModel([FakeSurface('a')], [FakeSurface('f')]))
    values = make(manager, ['stratigraphy_surfaces', 'fault_surfaces'])
    seen = set()
    for value in values:
        if isinstance(value, Group):
            assert value.parent is None or value.parent in seen
            seen.add(value.id)
        elif isinstance(value, Item):
            assert value.parent in seen
    assert 'loopstructural/model' in seen
    assert all(v.id.startswith(scene.ID_PREFIX) for v in values)


def test_surfaces_have_colours_and_faults_are_red():
    manager = FakeManager(FakeModel([FakeSurface('a', colour='#0000ff')], [FakeSurface('f')]))
    items = by_id(make(manager, ['stratigraphy_surfaces', 'fault_surfaces']))
    strat = items['loopstructural/model/stratigraphy/a']
    fault = items['loopstructural/model/faults/f']
    assert isinstance(strat.obj, Surface) and strat.colour == (0, 0, 255)
    assert fault.colour == scene.FAULT_COLOUR


def test_only_the_selected_kinds_are_made():
    manager = FakeManager(FakeModel([FakeSurface('a')], [FakeSurface('f')]))
    ids = [v.id for v in make(manager, ['stratigraphy_surfaces'])]
    assert 'loopstructural/model/faults' not in ids
    assert 'loopstructural/model/stratigraphy/a' in ids


def test_same_name_gets_a_suffix_and_empty_surface_is_left_out():
    manager = FakeManager(
        FakeModel([FakeSurface('a'), FakeSurface('a'), FakeSurface('b', pv.PolyData())])
    )
    ids = [v.id for v in make(manager, ['stratigraphy_surfaces']) if isinstance(v, Item)]
    assert ids == ['loopstructural/model/stratigraphy/a', 'loopstructural/model/stratigraphy/a_2']


def test_no_model_and_no_kind_are_errors():
    with pytest.raises(scene.PushError, match='no model'):
        make(SimpleNamespace(model=None), ['dem'])
    with pytest.raises(scene.PushError, match='at least one'):
        make(FakeManager(FakeModel()), [])
    with pytest.raises(scene.PushError, match='cells'):
        make(FakeManager(FakeModel()), ['dem'], ncells=(0, 2, 2))


def test_stratigraphy_volume_is_a_categorical_block_model():
    manager = FakeManager(FakeModel())
    item = by_id(make(manager, ['stratigraphy_volume'], ncells=(4, 3, 2)))[
        'loopstructural/model/volume/stratigraphy'
    ]
    block = item.obj
    assert isinstance(block, BlockModel)
    assert tuple(block.cells) == (4, 3, 2)
    unit = block.cell_properties['unit']
    assert isinstance(unit, Categorical)
    assert list(unit.names) == ['young', 'old', scene.NO_UNIT_NAME]
    assert len(unit.codes) == 24
    # x changes fastest and z slowest: the first 12 cells are the lower layer
    assert set(unit.codes[:12]) == {1}  # z centre -75, in 'old'
    assert set(unit.codes[12:]) == {0}  # z centre -25, in 'young'
    assert unit.colours[0] == (255, 0, 0, 255)
    assert unit.colours[-1] == scene.NO_UNIT_COLOUR


def test_volume_is_skipped_when_there_are_no_units():
    manager = FakeManager(FakeModel(), units=())
    values = make(manager, ['stratigraphy_volume'])
    assert [v for v in values if isinstance(v, Skipped)]
    assert not [v for v in values if isinstance(v, Item)]


def test_scalar_fields_have_node_values_in_x_fastest_order():
    model = FakeModel(features=[FakeFeature('s0'), FakeFeature('bad'), FakeFeature('__hidden')])
    values = make(FakeManager(model), ['scalar_fields'], ncells=(2, 2, 3))
    items = by_id(values)
    block = items['loopstructural/model/scalar_fields/s0'].obj
    assert block.properties['value'].shape == (3 * 3 * 4,)
    # the value is the z of the node, and z is the slowest axis
    expected = np.repeat(ORIGIN[2] + np.arange(4) * (MAXIMUM[2] - ORIGIN[2]) / 3, 9)
    assert np.allclose(block.properties['value'], expected)
    assert 'loopstructural/model/scalar_fields/__hidden' not in items
    skipped = [v for v in values if isinstance(v, Skipped)]
    assert len(skipped) == 1 and 'cannot evaluate' in skipped[0].reason


def test_dem_is_a_surface_with_an_elevation_and_drops_missing_values():
    def dem(x, y):
        z = np.full_like(x, 10.0)
        z[:2, :2] = np.nan
        return z

    manager = FakeManager(FakeModel(), dem=dem)
    surface = by_id(make(manager, ['dem'], dem_resolution=6))['loopstructural/model/dem/dem'].obj
    assert isinstance(surface, Surface)
    assert np.all(np.isfinite(surface.vertices))
    assert np.allclose(surface.properties['elevation'], surface.vertices[:, 2])
    assert surface.triangles.max() < len(surface.vertices)
    # the normals point up
    a, b, c = (surface.vertices[surface.triangles[:, i]] for i in range(3))
    assert np.all(np.cross(b - a, c - a)[:, 2] > 0)


def test_dem_with_no_value_is_skipped():
    manager = FakeManager(FakeModel(), dem=lambda x, y: np.full_like(x, np.nan))
    values = make(manager, ['dem'])
    assert [v for v in values if isinstance(v, Skipped)]


def test_points_and_orientation_data_are_separate_kinds():
    locations = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    values = SimpleNamespace(name='s0', locations=locations, values=np.array([0.0, 1.0, np.nan]))
    vectors = SimpleNamespace(
        name='s0+_gradient',
        locations=locations,
        vectors=np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 0.0], [1.0, 0.0, 1.0]]),
    )
    model = FakeModel(features=[FakeFeature('s0', [values, vectors])])
    manager = FakeManager(model)
    points = by_id(make(manager, ['points']))['loopstructural/model/points/s0/s0'].obj
    assert isinstance(points, Points) and len(points.vertices) == 3
    assert np.array_equal(points.properties['value'][:2], [0.0, 1.0])
    vec = by_id(make(manager, ['vectors']))['loopstructural/model/vectors/s0/s0_gradient'].obj
    assert isinstance(vec, Vectors)
    # the zero vector is dropped
    assert len(vec.vertices) == 2
    _dip_direction, dip = vec.orientation
    assert dip[0] == pytest.approx(0.0)  # a vertical normal is a flat plane
    assert dip[1] == pytest.approx(45.0)


def test_vector_field_is_reduced_to_the_limit():
    count = scene.MAX_VECTOR_FIELD_POINTS * 3
    rng = np.random.default_rng(0)
    field = SimpleNamespace(
        locations=rng.random((count, 3)) * 100, vectors=rng.random((count, 3)) + 0.1
    )
    model = FakeModel(features=[FakeFeature('s0', field=field), FakeFeature('s1')])
    values = make(FakeManager(model), ['vector_fields'])
    items = by_id(values)
    obj = items['loopstructural/model/vector_fields/s0'].obj
    assert isinstance(obj, Vectors)
    assert len(obj.vertices) <= scene.MAX_VECTOR_FIELD_POINTS
    assert [v.id for v in values if isinstance(v, Skipped)] == [
        'loopstructural/model/vector_fields/s1'
    ]


def test_lines_hold_the_bounding_box_and_the_layer_lines():
    trace = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [10.0, 10.0, 0.0]])
    sets = [scene.LineSet('fault_traces', 'Fault traces', [trace, trace[:1]])]
    items = by_id(make(FakeManager(FakeModel()), ['lines'], line_sets=sets))
    box = items['loopstructural/model/lines/bounding_box'].obj
    assert isinstance(box, Lines) and len(box.segments) == 12 and len(box.vertices) == 24
    traces = items['loopstructural/model/lines/fault_traces'].obj
    # the one-point line is ignored
    assert len(traces.vertices) == 3 and traces.segments.tolist() == [[0, 1], [1, 2]]


def test_empty_line_set_is_skipped():
    sets = [scene.LineSet('basal_contacts', 'Basal contacts', [])]
    values = make(FakeManager(FakeModel()), ['lines'], line_sets=sets)
    assert [v.id for v in values if isinstance(v, Skipped)] == [
        'loopstructural/model/lines/basal_contacts'
    ]


def test_world_locations_uses_the_version_near_the_model():
    class Shifted(FakeModel):
        def rescale(self, points):
            return np.asarray(points) + np.array([1000.0, 2000.0, -50.0])

    model = Shifted()
    near = np.array([[1000.0, 2000.0, -50.0]])
    far = np.array([[0.0, 0.0, 0.0]])
    assert np.array_equal(scene.world_locations(model, near), near)
    assert np.allclose(scene.world_locations(model, far), [[1000.0, 2000.0, -50.0]])
