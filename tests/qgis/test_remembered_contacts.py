"""Pytest tests for the contacts that the model reads with "Calculate from geology polygons".

The contacts layer of that mode is a memory layer that exists for display. It is
empty or gone when the project is opened again, so the model must not read it
again after the build calculated the contacts.
"""

from unittest.mock import Mock

import geopandas as gpd
import pytest
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsProject,
    QgsVectorLayer,
)
from shapely.geometry import LineString

from loopstructural.main import layer_roles
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.derived_refresh import BASAL_CONTACT_UNIT_FIELD
from loopstructural.main.model_manager import GeologicalModelManager


class _DebugManager:
    def log(self, *args, **kwargs):
        pass


@pytest.fixture
def project():
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem('EPSG:32755'))
    yield QgsProject.instance()
    QgsProject.instance().removeAllMapLayers()


@pytest.fixture
def data_manager(project):
    manager = ModellingDataManager(project=project, mapCanvas=Mock(), logger=Mock())
    manager.set_model_manager(GeologicalModelManager(debug_manager=_DebugManager()))
    column = manager.get_stratigraphic_column()
    column.clear(basement=False)
    for name in ('old', 'young'):
        column.add_unit(name=name, colour='#ff0000', where='top')
    return manager


def _contacts():
    lines = [LineString([(0, 0), (10, 0), (20, 5)]), LineString([(0, 50), (20, 50)])]
    return gpd.GeoDataFrame(
        {BASAL_CONTACT_UNIT_FIELD: ['old', 'young']}, geometry=lines, crs='EPSG:32755'
    )


def _empty_contacts_layer(project):
    layer = QgsVectorLayer(
        f'LineString?crs=EPSG:32755&field={BASAL_CONTACT_UNIT_FIELD}:string',
        'Basal contacts',
        'memory',
    )
    assert layer.isValid()
    project.addMapLayer(layer)
    return layer


def _rows(manager):
    return {
        name: len(unit.get('contact', ()))
        for name, unit in manager._model_manager.stratigraphy.items()
    }


class TestContactsFromGeology:
    def test_there_is_no_contact_data_before_the_first_calculation(self, data_manager):
        assert not data_manager.has_contact_data()

    def test_the_calculated_contacts_are_in_the_model(self, data_manager):
        data_manager.update_stratigraphy(
            basal_contacts=_contacts(), unit_name_field=BASAL_CONTACT_UNIT_FIELD
        )
        assert data_manager.has_contact_data()
        assert _rows(data_manager)['old'] > 0 and _rows(data_manager)['young'] > 0

    def test_a_later_update_keeps_the_calculated_contacts(self, data_manager):
        data_manager.update_stratigraphy(
            basal_contacts=_contacts(), unit_name_field=BASAL_CONTACT_UNIT_FIELD
        )
        before = _rows(data_manager)
        # a change of the column or of the orientations updates the stratigraphy with no argument
        data_manager.update_stratigraphy()
        assert _rows(data_manager) == before

    def test_an_empty_contacts_layer_does_not_remove_the_contacts(self, data_manager, project):
        data_manager.update_stratigraphy(
            basal_contacts=_contacts(), unit_name_field=BASAL_CONTACT_UNIT_FIELD
        )
        before = _rows(data_manager)
        # what the project has after it was opened again: the layer has no features
        data_manager.set_basal_contacts(
            _empty_contacts_layer(project), unitname_field=BASAL_CONTACT_UNIT_FIELD
        )
        assert _rows(data_manager) == before

    def test_the_contacts_layer_is_read_once(self, data_manager, project):
        layer = _empty_contacts_layer(project)
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt('LineString (0 0, 10 0, 20 5)'))
        feature.setAttribute(BASAL_CONTACT_UNIT_FIELD, 'old')
        layer.dataProvider().addFeatures([feature])
        data_manager.set_basal_contacts(layer, unitname_field=BASAL_CONTACT_UNIT_FIELD)
        assert _rows(data_manager)['old'] > 0
        # the layer changes: the model keeps what was read, until the build calculates again
        layer.dataProvider().truncate()
        data_manager.update_stratigraphy()
        assert _rows(data_manager)['old'] > 0

    def test_a_new_project_forgets_the_contacts(self, data_manager):
        data_manager.update_stratigraphy(
            basal_contacts=_contacts(), unit_name_field=BASAL_CONTACT_UNIT_FIELD
        )
        data_manager.set_basal_contacts(None, unitname_field=None)
        data_manager.update_stratigraphy()
        assert data_manager._calculated_contacts is None


class TestContactsFromLayer:
    def test_the_layer_of_the_user_is_not_remembered(self, data_manager, project):
        data_manager.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        data_manager.set_basal_contacts(
            _empty_contacts_layer(project), unitname_field=BASAL_CONTACT_UNIT_FIELD
        )
        assert data_manager._calculated_contacts is None


class TestDeletedLayer:
    """A setting that points to a layer that QGIS deleted must not raise."""

    @staticmethod
    def _delete(data_manager, project):
        layer = _empty_contacts_layer(project)
        data_manager.set_basal_contacts(layer, unitname_field=BASAL_CONTACT_UNIT_FIELD)
        project.removeMapLayer(layer.id())
        return layer

    def test_the_unique_units_do_not_raise(self, data_manager, project):
        self._delete(data_manager, project)
        assert data_manager.calculate_unique_basal_units() == 0
        assert data_manager.get_basal_contacts() is None

    def test_the_stratigraphy_update_does_not_raise(self, data_manager, project):
        self._delete(data_manager, project)
        data_manager.update_stratigraphy()

    def test_the_getter_gives_nothing_for_a_deleted_layer(self, data_manager, project):
        self._delete(data_manager, project)
        assert data_manager.get_basal_contacts() is None
        # the next layer works as usual
        layer = _empty_contacts_layer(project)
        data_manager.set_basal_contacts(layer, unitname_field=BASAL_CONTACT_UNIT_FIELD)
        assert data_manager.get_basal_contacts()['layer'] is layer
