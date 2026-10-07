"""Pytest tests for the two workflows of the model manager.

With "constraints", the model has only the features that the user added. The
column and the fault traces keep their data, but the build does not use it.
With "map", the model has the generated features and the features that the
user added.
"""

import numpy as np
import pandas as pd
import pytest
from LoopStructural import StratigraphicColumn
from LoopStructural.datatypes import BoundingBox

from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.main.workflow_mode import WORKFLOW_MODE_CONSTRAINTS, WORKFLOW_MODE_MAP
from loopstructural.toolbelt.preferences import PlgSettingsStructure

POINTS = [(x, y) for x in (20.0, 50.0, 80.0) for y in (20.0, 50.0, 80.0)]


def _value_layer():
    import geopandas as gpd
    from shapely.geometry import Point

    points = [Point(x, y, 0.0) for x, y in POINTS]
    gdf = gpd.GeoDataFrame({'value': [p.x / 10.0 for p in points]}, geometry=points)
    return {'layer_name': 'values', 'type': 'Value', 'value_field': 'value', 'df': gdf}


def _contact(z):
    return pd.DataFrame({'X': [20.0, 50.0, 80.0], 'Y': [20.0, 50.0, 80.0], 'Z': [z, z, z]})


def _orientations():
    return pd.DataFrame({'X': [50.0], 'Y': [50.0], 'Z': [0.0], 'dip': [0.0], 'strike': [0.0]})


class _DebugManager:
    def log(self, *args, **kwargs):
        pass


def _one_group_column():
    column = StratigraphicColumn()
    column.clear(basement=False)
    column.add_unit(name='lower', thickness=20.0, where='top')
    column.add_unit(name='upper', thickness=20.0, where='top')
    return column


@pytest.fixture
def manager(monkeypatch):
    """A manager with a column, contacts and one fault trace, and one manual foliation."""
    monkeypatch.setattr(PlgSettingsStructure, 'interpolator_nelements', 200)
    manager = GeologicalModelManager(debug_manager=_DebugManager())
    manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
    manager.stratigraphic_column = _one_group_column()
    manager.stratigraphy['lower']['contact'] = _contact(-10.0)
    manager.stratigraphy['upper']['contact'] = _contact(10.0)
    manager.stratigraphy['upper']['orientations'] = _orientations()
    # the fault build itself is not under test here
    monkeypatch.setattr(manager.model, 'create_and_add_fault', lambda *a, **k: None)
    manager.faults['f1']['data'] = pd.DataFrame(
        {'X': [10.0, 90.0], 'Y': [50.0, 50.0], 'Z': [0.0, 0.0]}
    )
    manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
    return manager


def _feature_names(manager):
    return [f.name for f in manager.features() if not f.name.startswith('__')]


class TestBuild:
    def test_constraints_build_only_the_manual_features(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        manager.update_model(notify_observers=False)
        assert _feature_names(manager) == ['s1']

    def test_map_builds_the_generated_and_the_manual_features(self, manager):
        manager.update_model(notify_observers=False)
        group_name = manager.stratigraphic_column.get_groups()[0].name
        assert group_name in _feature_names(manager)
        assert 's1' in _feature_names(manager)

    def test_the_data_stays_when_the_mode_changes(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        manager.update_model(notify_observers=False)
        assert 'f1' in manager.faults
        assert not manager.stratigraphy['lower']['contact'].empty
        manager.set_workflow_mode(WORKFLOW_MODE_MAP)
        manager.update_model(notify_observers=False)
        group_name = manager.stratigraphic_column.get_groups()[0].name
        assert group_name in _feature_names(manager)

    def test_generated_feature_names_are_empty_with_constraints(self, manager):
        assert manager.generated_feature_names()
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        assert manager.generated_feature_names() == []

    def test_an_unknown_mode_is_an_error(self, manager):
        with pytest.raises(ValueError):
            manager.set_workflow_mode('other')


class TestState:
    def test_a_column_change_does_not_make_a_constraints_model_stale(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        manager.update_model(notify_observers=False)
        manager.update_all_features(notify_observers=False)
        assert manager.model_state == 'solved'
        manager.stratigraphic_column.add_unconformity(name='new', where='top')
        assert manager.model_state == 'solved'

    def test_a_column_change_makes_a_map_model_stale(self, manager):
        manager.set_stratigraphic_column(manager.stratigraphic_column)
        manager.update_model(notify_observers=False)
        manager.stratigraphic_column.add_unconformity(name='new', where='top')
        assert manager.model_state == 'stale'

    def test_a_change_of_the_mode_makes_a_built_model_stale(self, manager):
        manager.update_model(notify_observers=False)
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        assert manager.model_state == 'stale'

    def test_a_change_of_the_mode_of_an_empty_model_is_not_stale(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        assert manager.model_state == 'empty'

    def test_the_same_mode_does_not_make_the_model_stale(self, manager):
        manager.update_model(notify_observers=False)
        manager.set_workflow_mode(WORKFLOW_MODE_MAP)
        assert manager.model_state != 'stale'


class TestRefresh:
    def test_edited_contacts_do_not_change_a_constraints_model(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        manager.update_model(notify_observers=False)
        manager.stratigraphy['lower']['contact'] = _contact(-20.0)
        manager.faults['f1']['data'] = pd.DataFrame(
            {'X': [10.0, 90.0], 'Y': [40.0, 60.0], 'Z': [0.0, 0.0]}
        )

        result = manager.refresh_feature_data()

        assert result == {'updated': [], 'needs_initialize': []}
        assert manager.model_state != 'stale'

    def test_the_manual_foliation_is_still_refreshed(self, manager):
        manager.set_workflow_mode(WORKFLOW_MODE_CONSTRAINTS)
        manager.update_model(notify_observers=False)
        layer = _value_layer()
        layer['df']['value'] = layer['df']['value'] * 2.0
        manager.manual_foliations['s1']['data']['values'] = layer

        result = manager.refresh_feature_data()

        assert result['updated'] == ['s1']
        manager.update_all_features(notify_observers=False)
        value = manager.model['s1'].evaluate_value(np.array([[50.0, 50.0, 0.0]]))
        assert np.isfinite(value).all()
