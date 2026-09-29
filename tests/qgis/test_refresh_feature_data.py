"""Pytest tests for putting changed input data into an existing model.

`GeologicalModelManager.refresh_feature_data` puts the current input data
into the features that are already in the model, so the changes the user
made to those features stay (Initialize Model builds every feature again).
`ModellingDataManager` watches the input layers and reads the changed ones
again before that.
"""

from unittest.mock import Mock

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from LoopStructural import StratigraphicColumn
from LoopStructural.datatypes import BoundingBox
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsProject,
    QgsVectorLayer,
)
from shapely.geometry import Point

from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure

MODEL_CRS = "EPSG:32755"
POINTS = [(x, y) for x in (20.0, 50.0, 80.0) for y in (20.0, 50.0, 80.0)]


def _value_layer(scale=10.0):
    points = [Point(x, y, 0.0) for x, y in POINTS]
    gdf = gpd.GeoDataFrame({'value': [p.x / scale for p in points]}, geometry=points)
    return {'layer_name': 'values', 'type': 'Value', 'value_field': 'value', 'df': gdf}


def _contact(z):
    return pd.DataFrame({'X': [20.0, 50.0, 80.0], 'Y': [20.0, 50.0, 80.0], 'Z': [z, z, z]})


def _orientations():
    return pd.DataFrame({'X': [50.0], 'Y': [50.0], 'Z': [0.0], 'dip': [0.0], 'strike': [0.0]})


class _DebugManager:
    """update_model logs through the debug manager, which the plugin always sets."""

    def log(self, *args, **kwargs):
        pass


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(PlgSettingsStructure, 'interpolator_nelements', 200)
    manager = GeologicalModelManager(debug_manager=_DebugManager())
    manager.update_bounding_box(BoundingBox(origin=[0, 0, -50], maximum=[100, 100, 50]))
    manager.stratigraphic_column = StratigraphicColumn()
    return manager


def _one_group_column():
    column = StratigraphicColumn()
    column.clear(basement=False)
    column.add_unit(name='lower', thickness=20.0, where='top')
    column.add_unit(name='upper', thickness=20.0, where='top')
    return column


class TestRefreshManualFoliation:
    def test_changed_data_goes_into_the_same_feature(self, manager):
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        manager.update_all_features(notify_observers=False)
        feature = manager.model['s1']
        before = feature.evaluate_value(np.array([[50.0, 50.0, 0.0]]))

        manager.manual_foliations['s1']['data']['values'] = _value_layer(scale=1.0)
        result = manager.refresh_feature_data()

        assert result == {'updated': ['s1'], 'needs_initialize': []}
        assert manager.model['s1'] is feature
        assert manager.is_feature_built(feature) is False
        assert manager.model_state == 'initialized'
        manager.update_all_features(notify_observers=False)
        after = feature.evaluate_value(np.array([[50.0, 50.0, 0.0]]))
        assert not np.allclose(before, after)

    def test_unchanged_data_keeps_the_feature_built(self, manager):
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        manager.update_all_features(notify_observers=False)

        result = manager.refresh_feature_data()

        assert result == {'updated': [], 'needs_initialize': []}
        assert manager.is_feature_built(manager.model['s1']) is True


class TestRefreshStratigraphy:
    def test_changed_contacts_go_into_the_group_foliation(self, manager):
        manager.stratigraphic_column = _one_group_column()
        manager.stratigraphy['lower']['contact'] = _contact(-10.0)
        manager.stratigraphy['upper']['contact'] = _contact(10.0)
        manager.stratigraphy['upper']['orientations'] = _orientations()
        manager.update_model(notify_observers=False)
        group_name = manager.stratigraphic_column.get_groups()[0].name
        feature = manager.model[group_name]

        manager.stratigraphy['lower']['contact'] = _contact(-20.0)
        result = manager.refresh_feature_data()

        assert result == {'updated': [group_name], 'needs_initialize': []}
        assert manager.model[group_name] is feature
        assert (feature.builder.data['Z'] == -20.0).any()

    def test_group_with_new_data_needs_initialize(self, manager):
        manager.stratigraphic_column = _one_group_column()
        manager.update_model(notify_observers=False)
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        group_name = manager.stratigraphic_column.get_groups()[0].name

        manager.stratigraphy['lower']['contact'] = _contact(-10.0)
        result = manager.refresh_feature_data()

        assert result['needs_initialize'] == [group_name]
        assert manager.model_state == 'stale'


class TestRefreshFaults:
    @pytest.fixture
    def fault_manager(self, manager, monkeypatch):
        # the fault build itself is not under test here
        monkeypatch.setattr(manager.model, 'create_and_add_fault', lambda *a, **k: None)
        manager.faults['f1']['data'] = pd.DataFrame(
            {'X': [10.0, 90.0], 'Y': [50.0, 50.0], 'Z': [0.0, 0.0]}
        )
        manager.add_foliation('s1', {'values': _value_layer()}, use_z_coordinate=True)
        manager.update_model(notify_observers=False)
        return manager

    def test_unchanged_fault_needs_nothing(self, fault_manager):
        result = fault_manager.refresh_feature_data()

        assert result['needs_initialize'] == []
        assert fault_manager.model_state != 'stale'

    def test_changed_fault_trace_needs_initialize(self, fault_manager):
        fault_manager.faults['f1']['data'] = pd.DataFrame(
            {'X': [10.0, 90.0], 'Y': [40.0, 60.0], 'Z': [0.0, 0.0]}
        )

        result = fault_manager.refresh_feature_data()

        assert result['needs_initialize'] == ['f1']
        assert fault_manager.model_state == 'stale'
        fault_manager.update_model(notify_observers=False)
        assert fault_manager.model_state != 'stale'


@pytest.fixture
def value_layer():
    """A point layer with a 'value' field, in the project like a real input layer."""
    layer = QgsVectorLayer(f"PointZ?crs={MODEL_CRS}&field=value:double", 'values', "memory")
    features = []
    for x, y in POINTS:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry(QgsPoint(x, y, 0.0)))
        feature.setAttributes([x / 10.0])
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    QgsProject.instance().addMapLayer(layer)
    layer_id = layer.id()
    yield layer
    if QgsProject.instance().mapLayer(layer_id) is not None:
        QgsProject.instance().removeMapLayer(layer_id)


@pytest.fixture
def data_manager(manager):
    data_manager = ModellingDataManager(
        project=QgsProject.instance(), mapCanvas=Mock(), logger=Mock()
    )
    data_manager.set_model_manager(manager)
    data_manager.set_model_crs(QgsCoordinateReferenceSystem(MODEL_CRS), use_project_crs=False)
    return data_manager


def _add_foliation_from_layer(data_manager, layer):
    data_manager.update_feature_data(
        's1', {'layer': layer, 'layer_name': layer.name(), 'type': 'Value', 'value_field': 'value'}
    )
    data_manager.add_foliation_to_model('s1')


def _double_values(layer):
    layer.startEditing()
    for feature in layer.getFeatures():
        layer.changeAttributeValue(feature.id(), 0, feature['value'] * 2.0)
    assert layer.commitChanges()


class TestLayerWatching:
    def test_changed_layer_is_flagged(self, data_manager, value_layer):
        layer = value_layer
        _add_foliation_from_layer(data_manager, layer)
        callback = Mock()
        data_manager.add_layer_data_changed_callback(callback)
        assert data_manager.get_changed_layers() == []

        _double_values(layer)

        assert data_manager.get_changed_layers() == ['values']
        callback.assert_called()

    def test_edit_in_the_edit_buffer_is_flagged(self, data_manager, value_layer):
        layer = value_layer
        _add_foliation_from_layer(data_manager, layer)

        layer.startEditing()
        feature = next(layer.getFeatures())
        layer.changeAttributeValue(feature.id(), 0, 100.0)

        assert data_manager.get_changed_layers() == ['values']
        layer.rollBack()

    def test_refresh_model_data_updates_the_foliation(self, data_manager, manager, value_layer):
        layer = value_layer
        _add_foliation_from_layer(data_manager, layer)
        manager.update_all_features(notify_observers=False)
        feature = manager.model['s1']

        _double_values(layer)
        result = data_manager.refresh_model_data()

        assert result['updated'] == ['s1']
        assert manager.model['s1'] is feature
        assert data_manager.get_changed_layers() == []
        df = manager.manual_foliations['s1']['data']['values']['df']
        assert sorted(df['value']) == sorted(2.0 * x / 10.0 for x, _ in POINTS)

    def test_removed_layer_is_not_watched(self, data_manager, value_layer):
        layer = value_layer
        _add_foliation_from_layer(data_manager, layer)
        _double_values(layer)
        assert data_manager.get_changed_layers() == ['values']

        QgsProject.instance().removeMapLayer(layer.id())

        assert data_manager.get_changed_layers() == []
        assert data_manager._watched_layers == {}
