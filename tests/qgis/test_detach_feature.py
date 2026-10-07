"""Pytest tests for detaching a feature that the stratigraphic column makes.

A detached feature keeps a copy of its contact and orientation data. Rows that
the user adds to a generated feature are used together with the data of the
column.
"""

import geopandas as gpd
import pandas as pd
import pytest
from LoopStructural import StratigraphicColumn

from loopstructural.main.model_manager import GeologicalModelManager


def _contact(x):
    return pd.DataFrame({'X': [x], 'Y': [0.0], 'Z': [0.0]})


@pytest.fixture
def manager(monkeypatch):
    manager = GeologicalModelManager()
    captured = []

    def fake_create_and_add_foliation(name, data=None, **kwargs):
        captured.append((name, data, kwargs))
        return object()

    monkeypatch.setattr(manager.model, 'create_and_add_foliation', fake_create_and_add_foliation)
    monkeypatch.setattr(manager.model, 'add_unconformity', lambda *a, **k: None)
    manager._captured = captured

    column = StratigraphicColumn()
    column.clear(basement=False)
    column.add_unit(name='oldest', thickness=100.0, where='top')
    column.add_unit(name='youngest', thickness=200.0, where='top')
    manager.stratigraphic_column = column
    manager.stratigraphy['oldest']['contact'] = _contact(1.0)
    manager.stratigraphy['youngest']['contact'] = _contact(2.0)
    return manager


def _group_name(manager):
    return manager.stratigraphic_column.get_groups()[0].name


def _built_x(manager):
    manager.update_foliation_features()
    return sorted(manager._captured[-1][1]['X'])


class TestDetach:
    def test_a_group_of_the_column_is_a_generated_feature(self, manager):
        assert manager.is_generated(_group_name(manager))
        assert not manager.is_generated('other')

    def test_a_detached_feature_keeps_its_data(self, manager):
        name = _group_name(manager)
        assert manager.detach_feature(name)
        manager.stratigraphy['oldest']['contact'] = _contact(99.0)
        assert _built_x(manager) == [1.0, 2.0]

    def test_a_feature_that_is_not_detached_follows_the_contacts(self, manager):
        manager.stratigraphy['oldest']['contact'] = _contact(99.0)
        assert _built_x(manager) == [2.0, 99.0]

    def test_a_feature_without_data_cannot_be_detached(self, manager):
        manager.stratigraphy.clear()
        assert not manager.detach_feature(_group_name(manager))

    def test_a_feature_that_is_not_generated_cannot_be_detached(self, manager):
        assert not manager.detach_feature('other')

    def test_attach_follows_the_column_again_and_the_model_is_stale(self, manager):
        name = _group_name(manager)
        manager.detach_feature(name)
        manager.stratigraphy['oldest']['contact'] = _contact(99.0)
        assert manager.attach_feature(name)
        assert _built_x(manager) == [2.0, 99.0]
        assert manager._data_dirty

    def test_the_detached_data_is_saved_and_loaded(self, manager):
        name = _group_name(manager)
        manager.detach_feature(name)
        written = manager.detached_to_dict()
        manager.detached = {}
        manager.detached_from_dict(written)
        assert manager.is_detached(name)
        assert sorted(manager.detached[name]['X']) == [1.0, 2.0]

    def test_reset_forgets_detached_features(self, manager):
        manager.detach_feature(_group_name(manager))
        manager.reset()
        assert manager.detached == {}


class TestAddedRows:
    def _extra(self, x):
        layer = {
            'layer_name': 'values',
            'type': 'Value',
            'value_field': 'v',
            'df': gpd.GeoDataFrame({'v': [5.0]}, geometry=gpd.points_from_xy([x], [0.0])),
        }
        return {'data': {'values': layer}, 'use_z_coordinate': False}

    def test_added_rows_are_used_with_the_data_of_the_column(self, manager):
        name = _group_name(manager)
        manager.extra_constraints[name] = self._extra(7.0)
        assert _built_x(manager) == [1.0, 2.0, 7.0]

    def test_added_rows_stay_when_a_feature_is_detached(self, manager):
        name = _group_name(manager)
        manager.extra_constraints[name] = self._extra(7.0)
        manager.detach_feature(name)
        # the copy has the data of the column only
        assert sorted(manager.detached[name]['X']) == [1.0, 2.0]
        assert _built_x(manager) == [1.0, 2.0, 7.0]

    def test_an_inequality_row_gives_the_solver(self, manager):
        name = _group_name(manager)
        spec = self._extra(7.0)
        spec['data']['values'].update(
            {'type': 'Inequality', 'lower_field': 'v', 'upper_field': 'v'}
        )
        manager.extra_constraints[name] = spec
        manager.update_foliation_features()
        assert manager._captured[-1][2]['solver'] == 'admm'
