"""A change to the structure of the stratigraphic column (its unconformities,
the order of its elements, or the fault link or polarity of a boundary) is
only built by Initialize Model. These tests make sure that such a change
marks the model as 'stale', and that a change to a unit only does not.
"""

from unittest.mock import Mock

import pytest
from LoopStructural import StratigraphicColumn
from qgis.core import QgsProject

from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager


class _FakeBuilder:
    _up_to_date = True
    faults = []


class _FakeFeature:
    def __init__(self, name):
        self.name = name
        self.builder = _FakeBuilder()


def _column():
    column = StratigraphicColumn()
    column.clear(basement=False)
    column.add_unit(name='lower', thickness=50.0, where='top')
    boundary = column.add_unconformity(name='boundary', where='top')
    upper = column.add_unit(name='upper', thickness=80.0, where='top')
    return column, boundary, upper


@pytest.fixture
def manager():
    manager = GeologicalModelManager()
    column, boundary, upper = _column()
    manager.set_stratigraphic_column(column)
    # a solved model, so that 'stale' is not hidden by 'empty'
    manager.model.features = [_FakeFeature('a')]
    manager._boundary = boundary
    manager._upper = upper
    assert manager.model_state == 'solved'
    return manager


class TestColumnChangeMarksModelStale:
    def test_adding_an_unconformity(self, manager):
        manager.stratigraphic_column.add_unconformity(name='new', where='top')
        assert manager.model_state == 'stale'

    def test_removing_an_element(self, manager):
        manager.stratigraphic_column.remove_unit(uuid=manager._boundary.uuid)
        assert manager.model_state == 'stale'

    def test_changing_the_order(self, manager):
        column = manager.stratigraphic_column
        manager.stratigraphic_column.update_order([e.uuid for e in reversed(column.order)])
        assert manager.model_state == 'stale'

    def test_changing_the_unconformity_type(self, manager):
        manager.stratigraphic_column.update_element(
            {'uuid': manager._boundary.uuid, 'unconformity_type': 'onlap'}
        )
        assert manager.model_state == 'stale'

    def test_changing_a_unit_only_does_not_mark_stale(self, manager):
        manager.stratigraphic_column.update_element(
            {'uuid': manager._upper.uuid, 'name': 'upper', 'thickness': 90.0}
        )
        assert manager.model_state == 'solved'

    def test_update_model_clears_the_flag(self, manager):
        manager.mark_column_changed()
        assert manager.model_state == 'stale'
        manager._debug_manager = Mock()
        manager.update_model(notify_observers=False)
        assert manager._column_dirty is False

    def test_a_new_column_replaces_the_observed_column(self, manager):
        old_column = manager.stratigraphic_column
        new_column, _boundary, _upper = _column()
        manager.set_stratigraphic_column(new_column)
        manager._column_dirty = False
        old_column.add_unconformity(name='old', where='top')
        assert manager.model_state == 'solved'
        new_column.add_unconformity(name='new', where='top')
        assert manager.model_state == 'stale'


@pytest.fixture
def data_manager(manager):
    data_manager = ModellingDataManager(
        project=QgsProject.instance(), mapCanvas=Mock(), logger=Mock()
    )
    data_manager.set_model_manager(manager)
    manager._column_dirty = False
    return data_manager


class TestFaultBoundaryMarksModelStale:
    def test_linking_a_fault(self, manager, data_manager):
        data_manager.set_fault_boundary('uuid', 'fault_a')
        assert manager.model_state == 'stale'

    def test_flipping_the_polarity(self, manager, data_manager):
        data_manager.set_fault_boundary('uuid', 'fault_a')
        manager._column_dirty = False
        data_manager.set_fault_boundary('uuid', 'fault_a', flipped=True)
        assert data_manager.is_fault_boundary_flipped('uuid')
        assert manager.flipped_fault_boundaries == {'uuid'}
        assert manager.model_state == 'stale'

    def test_same_link_again_does_not_mark_stale(self, manager, data_manager):
        data_manager.set_fault_boundary('uuid', 'fault_a', flipped=True)
        manager._column_dirty = False
        data_manager.set_fault_boundary('uuid', 'fault_a', flipped=True)
        assert manager.model_state == 'solved'

    def test_clearing_a_fault_link(self, manager, data_manager):
        data_manager.set_fault_boundary('uuid', 'fault_a', flipped=True)
        manager._column_dirty = False
        data_manager.clear_fault_boundary('uuid')
        assert not data_manager.is_fault_boundary_flipped('uuid')
        assert manager.model_state == 'stale'

    def test_flip_is_saved_and_loaded(self, data_manager):
        data_manager.set_fault_boundary('uuid', 'fault_a', flipped=True)
        saved = data_manager.to_dict()
        assert saved['flipped_fault_boundaries'] == ['uuid']
        data_manager.clear_fault_boundary('uuid')
        data_manager.update_from_dict(saved)
        assert data_manager.is_fault_boundary_flipped('uuid')
