"""Pytest tests for the fault topology calculation.

The module has no QGIS code, so the tests use traces from shapely and run in
the fast tests/unit/ job.
"""

import pytest
from LoopStructural import FaultTopology, StratigraphicColumn
from LoopStructural.modelling.core.fault_topology import FaultRelationshipType
from shapely.geometry import LineString

from loopstructural.main import fault_topology_calc as calc

ABUTTING = FaultRelationshipType.ABUTTING
FAULTED = FaultRelationshipType.FAULTED


def t_junction():
    """Fault "stem" ends on the middle of fault "bar"."""
    bar = LineString([(0, 0), (10, 0)])
    stem = LineString([(5, 0), (5, 10)])
    return bar, stem


def test_t_junction_stem_abuts():
    bar, stem = t_junction()
    assert calc.fault_pair_direction(stem, bar) == 0
    assert calc.fault_pair_direction(bar, stem) == 1


def test_input_order_gives_the_same_fault():
    bar, stem = t_junction()
    first = calc.fault_pair_direction(bar, stem)
    second = calc.fault_pair_direction(stem, bar)
    assert [bar, stem][first] is stem
    assert [stem, bar][second] is stem


def test_crossing_has_no_direction():
    a = LineString([(0, 5), (10, 5)])
    b = LineString([(5, 0), (5, 10)])
    assert calc.fault_pair_direction(a, b) is None


def test_separate_traces_have_no_direction():
    a = LineString([(0, 0), (1, 0)])
    b = LineString([(0, 5), (1, 5)])
    assert calc.fault_pair_direction(a, b) is None


def test_end_to_end_has_no_direction():
    a = LineString([(0, 0), (5, 0)])
    b = LineString([(5, 0), (10, 0)])
    assert calc.fault_pair_direction(a, b) is None


def make_topology():
    return FaultTopology(StratigraphicColumn())


def test_update_writes_the_abutting_fault_first():
    bar, stem = t_junction()
    topology = make_topology()
    # the table order is "bar" then "stem": the wrong way round
    result = calc.update_topology(topology, {'bar': bar, 'stem': stem}, [('bar', 'stem')])
    assert result.undetermined == [] and result.kept == []
    assert topology.adjacency == {('stem', 'bar'): ABUTTING}


def test_update_keeps_the_layer_order_of_the_faults():
    traces = {
        name: LineString([(i * 20, 0), (i * 20 + 1, 0)]) for i, name in enumerate(['10', '2', '1'])
    }
    topology = make_topology()
    calc.update_topology(topology, traces, [])
    assert topology.faults == ['10', '2', '1']


def test_pair_without_direction_is_listed():
    a = LineString([(0, 5), (10, 5)])
    b = LineString([(5, 0), (5, 10)])
    topology = make_topology()
    result = calc.update_topology(topology, {'a': a, 'b': b}, [('a', 'b')])
    assert result.undetermined == [('a', 'b')]
    assert topology.adjacency == {}


def test_second_calculation_keeps_user_relationship():
    bar, stem = t_junction()
    topology = make_topology()
    traces = {'bar': bar, 'stem': stem}
    auto_pairs = {}
    calc.update_topology(topology, traces, [('bar', 'stem')], auto_pairs=auto_pairs)
    topology.update_fault_relationship('stem', 'bar', FAULTED)
    result = calc.update_topology(topology, traces, [('bar', 'stem')], auto_pairs=auto_pairs)
    assert topology.adjacency == {('stem', 'bar'): FAULTED}
    # the pair of the user is kept, and it is not a pair without a direction
    assert result.kept == [('bar', 'stem')]
    assert result.undetermined == []
    assert auto_pairs == {}


def test_second_calculation_replaces_its_own_pairs():
    bar, stem = t_junction()
    topology = make_topology()
    auto_pairs = {}
    calc.update_topology(
        topology, {'bar': bar, 'stem': stem}, [('bar', 'stem')], auto_pairs=auto_pairs
    )
    assert auto_pairs == {('stem', 'bar'): ABUTTING}
    # the traces change: now "bar" ends on "stem"
    new_bar = LineString([(0, 5), (5, 5)])
    new_stem = LineString([(5, 0), (5, 10)])
    result = calc.update_topology(
        topology, {'bar': new_bar, 'stem': new_stem}, [('bar', 'stem')], auto_pairs=auto_pairs
    )
    assert topology.adjacency == {('bar', 'stem'): ABUTTING}
    assert auto_pairs == {('bar', 'stem'): ABUTTING}
    assert result.kept == []


def test_a_pair_that_is_not_found_again_is_removed():
    bar, stem = t_junction()
    topology = make_topology()
    auto_pairs = {}
    traces = {'bar': bar, 'stem': stem}
    calc.update_topology(topology, traces, [('bar', 'stem')], auto_pairs=auto_pairs)
    calc.update_topology(topology, traces, [], auto_pairs=auto_pairs)
    assert topology.adjacency == {}
    assert auto_pairs == {}


def test_duplicate_and_self_pairs_are_removed():
    assert calc.unique_pairs([('a', 'b'), ('b', 'a'), ('a', 'a'), (1, 2), ('1', '2')]) == [
        ('a', 'b'),
        ('1', '2'),
    ]


def test_the_tolerance_is_in_map_units():
    bar = LineString([(0, 0), (1000, 0)])
    # stops 5 map units short of "bar"
    stem = LineString([(500, 5), (500, 1000)])
    assert calc.fault_pair_direction(stem, bar, tolerance=10.0) == 0
    assert calc.fault_pair_direction(stem, bar, tolerance=1.0) is None


def test_an_overshoot_shorter_than_the_tolerance_abuts():
    bar = LineString([(0, 0), (1000, 0)])
    # goes 5 map units past "bar"
    stem = LineString([(500, -5), (500, 1000)])
    assert calc.fault_pair_direction(stem, bar, tolerance=10.0) == 0
    assert calc.fault_pair_direction(stem, bar, tolerance=1.0) is None


def test_user_relationship_in_the_other_direction_is_kept():
    bar, stem = t_junction()
    topology = make_topology()
    traces = {'bar': bar, 'stem': stem}
    calc.update_topology(topology, traces, [])
    topology.update_fault_relationship('bar', 'stem', FAULTED)
    calc.update_topology(topology, traces, [('bar', 'stem')])
    assert topology.adjacency == {('bar', 'stem'): FAULTED}


class FakeLayer:
    def __init__(self, features=()):
        self._features = list(features)

    def getFeatures(self):
        return iter(self._features)


class FakeCrs:
    def __init__(self, authid, geographic):
        self._authid = authid
        self._geographic = geographic

    def isValid(self):
        return True

    def authid(self):
        return self._authid

    def isGeographic(self):
        return self._geographic


class FakeLayerWithCrs(FakeLayer):
    def __init__(self, crs):
        super().__init__()
        self._crs = crs

    def crs(self):
        return self._crs


def test_layer_crs():
    assert calc._layer_crs(FakeLayer()) == (None, False)
    assert calc._layer_crs(FakeLayerWithCrs(FakeCrs('EPSG:28350', False))) == (
        'EPSG:28350',
        False,
    )
    assert calc._layer_crs(FakeLayerWithCrs(FakeCrs('EPSG:4326', True))) == ('EPSG:4326', True)


def test_missing_layer():
    with pytest.raises(calc.FaultTopologyError, match='fault layer'):
        calc.calculate_fault_topology(None, 'name', object())


def test_missing_field():
    with pytest.raises(calc.FaultTopologyError, match='field'):
        calc.calculate_fault_topology(FakeLayer(), '', object())


def test_empty_layer():
    pytest.importorskip('geopandas')
    with pytest.raises(calc.FaultTopologyError, match='no features'):
        calc.calculate_fault_topology(FakeLayer(), 'name', object())


def test_no_fault_layer_in_the_data_manager():
    class Manager:
        def get_fault_traces(self):
            return None

    with pytest.raises(calc.FaultTopologyError):
        calc.calculate_from_data_manager(Manager())


def test_result_message():
    text, warn = calc.result_message(calc.TopologyResult(12, []))
    assert text == "Calculated fault topology for 12 pairs." and not warn
    text, warn = calc.result_message(calc.TopologyResult(2, [('a', 'b')]))
    assert 'a-b' in text and warn
    text, warn = calc.result_message(calc.TopologyResult(2, [], [('c', 'd')]))
    assert 'c-d' in text and not warn
    text, warn = calc.result_message(calc.TopologyResult(2, [], [], ['The layer uses degrees.']))
    assert 'degrees' in text and warn
