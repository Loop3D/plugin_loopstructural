"""Pytest tests for the faults that the user gives by numbers (Add Fault).

The fault has no trace layer. `update_model` builds it together with the other
faults, so a fault that was added must be built again at each build.
"""

import json

import numpy as np
import pytest
from LoopStructural import StratigraphicColumn
from LoopStructural.datatypes import BoundingBox

from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure


class _DebugManager:
    def log(self, *args, **kwargs):
        pass


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(PlgSettingsStructure, 'interpolator_nelements', 200)
    manager = GeologicalModelManager(debug_manager=_DebugManager())
    manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
    manager.stratigraphic_column = StratigraphicColumn()
    return manager


def _spec(**changes):
    spec = {
        'name': 'F1',
        'strike': 0.0,
        'dip': 90.0,
        'pitch': 90.0,
        'displacement': 10.0,
        'centre': (50.0, 50.0, 0.0),
        'major_axis': 100.0,
        'intermediate_axis': 100.0,
        'minor_axis': 30.0,
    }
    spec.update(changes)
    return spec


def _names(manager):
    return [f.name for f in manager.model.features]


class TestParametricFault:
    def test_the_fault_is_built_by_update_model(self, manager):
        manager.add_parametric_fault(_spec())
        manager.update_model(notify_observers=False)
        assert 'F1' in _names(manager)

    def test_the_fault_surface_is_where_the_fault_is(self, manager):
        manager.add_parametric_fault(_spec())
        manager.update_model(notify_observers=False)
        manager.update_all_features(notify_observers=False)
        # the fault strikes north through x=50, so the field changes sign across it
        west = manager.model['F1'][0].evaluate_value(np.array([[30.0, 50.0, 0.0]]))
        east = manager.model['F1'][0].evaluate_value(np.array([[70.0, 50.0, 0.0]]))
        assert west[0] * east[0] < 0

    def test_adding_a_fault_makes_the_model_stale(self, manager):
        manager.add_parametric_fault(_spec())
        assert manager._data_dirty

    def test_a_name_that_is_used_is_an_error(self, manager):
        manager.add_parametric_fault(_spec())
        with pytest.raises(ValueError):
            manager.add_parametric_fault(_spec())

    def test_a_bad_fault_is_an_error(self, manager):
        with pytest.raises(ValueError):
            manager.add_parametric_fault(_spec(dip=0.0))

    def test_a_removed_fault_is_not_built_again(self, manager):
        manager.add_parametric_fault(_spec())
        manager.remove_parametric_fault('F1')
        manager.update_model(notify_observers=False)
        assert 'F1' not in _names(manager)

    def test_the_faults_are_saved_and_loaded(self, manager):
        manager.add_parametric_fault(_spec())
        written = json.loads(json.dumps(manager.parametric_faults_to_dict()))
        manager.parametric_faults = {}
        manager.parametric_faults_from_dict(written)
        manager.update_model(notify_observers=False)
        assert 'F1' in _names(manager)

    def test_reset_forgets_the_faults(self, manager):
        manager.add_parametric_fault(_spec())
        manager.reset()
        assert manager.parametric_faults == {}
