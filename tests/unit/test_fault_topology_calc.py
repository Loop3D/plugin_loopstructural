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
    skipped = calc.update_topology(topology, {'bar': bar, 'stem': stem}, [('bar', 'stem')])
    assert skipped == []
    assert topology.adjacency == {('stem', 'bar'): ABUTTING}


def test_update_keeps_the_layer_order_of_the_faults():
    traces = {name: LineString([(i * 20, 0), (i * 20 + 1, 0)]) for i, name in enumerate(['10', '2', '1'])}
    topology = make_topology()
    calc.update_topology(topology, traces, [])
    assert topology.faults == ['10', '2', '1']


def test_pair_without_direction_is_listed():
    a = LineString([(0, 5), (10, 5)])
    b = LineString([(5, 0), (5, 10)])
    topology = make_topology()
    skipped = calc.update_topology(topology, {'a': a, 'b': b}, [('a', 'b')])
    assert skipped == [('a', 'b')]
    assert topology.adjacency == {}


def test_second_calculation_keeps_user_relationship():
    bar, stem = t_junction()
    topology = make_topology()
    traces = {'bar': bar, 'stem': stem}
    calc.update_topology(topology, traces, [('bar', 'stem')])
    topology.update_fault_relationship('stem', 'bar', FAULTED)
    skipped = calc.update_topology(topology, traces, [('bar', 'stem')])
    assert topology.adjacency == {('stem', 'bar'): FAULTED}
    assert skipped == [('bar', 'stem')]


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
