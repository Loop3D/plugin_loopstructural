"""Pytest tests for rebuilding user-added foliations in update_model.

update_model clears the model features and builds the faults and the
stratigraphy again, so foliations added with add_foliation must be built
again from GeologicalModelManager.manual_foliations.
"""

import geopandas as gpd
import numpy as np
import pytest
from LoopStructural import StratigraphicColumn
from LoopStructural.datatypes import BoundingBox
from shapely.geometry import Point

from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure


def _value_layer():
    points = [Point(x, y, 0.0) for x in (20.0, 50.0, 80.0) for y in (20.0, 50.0, 80.0)]
    gdf = gpd.GeoDataFrame({'value': [p.x / 10.0 for p in points]}, geometry=points)
    return {'layer_name': 'values', 'type': 'Value', 'value_field': 'value', 'df': gdf}


class _DebugManager:
    """update_model logs through the debug manager, which the plugin always sets."""

    def log(self, *args, **kwargs):
        pass


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(PlgSettingsStructure, 'interpolator_nelements', 200)
    manager = GeologicalModelManager(debug_manager=_DebugManager())
    manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
    # the data manager always sets a column; update_model needs one
    manager.stratigraphic_column = StratigraphicColumn()
    return manager


def _names(manager):
    return [f.name for f in manager.model.features]


class TestManualFoliations:
    def test_foliation_is_built_again_by_update_model(self, manager):
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        assert 's1' in _names(manager)

        manager.update_model(notify_observers=False)

        assert 's1' in _names(manager)
        manager.update_all_features(notify_observers=False)
        values = manager.model['s1'].evaluate_value(np.array([[50.0, 50.0, 0.0]]))
        assert not np.any(np.isnan(values))

    def test_removed_foliation_is_not_built_again(self, manager):
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        manager.remove_manual_foliation('s1')

        manager.update_model(notify_observers=False)

        assert 's1' not in _names(manager)

    def test_rebuild_uses_the_options_it_was_added_with(self, manager):
        manager.add_foliation(
            's1',
            {'values': _value_layer()},
            use_z_coordinate=True,
            restrict_to_stratigraphic_domain=False,
        )

        spec = manager.manual_foliations['s1']
        assert spec['restrict_to_stratigraphic_domain'] is False
        assert spec['use_z_coordinate'] is True

    def test_later_edits_to_the_input_do_not_change_the_rebuild(self, manager):
        data = {'values': _value_layer()}
        manager.add_foliation('s1', data, use_z_coordinate=True)

        data['values']['type'] = 'Unknown'

        manager.update_model(notify_observers=False)
        assert 's1' in _names(manager)

    def test_reset_forgets_manual_foliations(self, manager):
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)

        manager.reset()

        assert manager.manual_foliations == {}
