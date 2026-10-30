"""Pytest tests for the source layers of step 2 (`StratigraphicLayersWidget`)."""

import pytest
from qgis.core import QgsProject, QgsVectorLayer
from qgis.testing import start_app

from loopstructural.main import layer_roles
from loopstructural.main.layer_roles import LayerRoles


class _DataManager:
    """The parts of the data manager that the widget uses."""

    def __init__(self):
        self.layer_roles = LayerRoles()
        self.layer_roles.contacts_source = layer_roles.CONTACTS_FROM_LAYER
        self._basal_contacts = None
        self.basal_contacts_calls = []
        self.settings = {}

    def set_basal_contacts_callback(self, callback):
        pass

    def set_structural_orientations_callback(self, callback):
        pass

    def find_layer_by_name(self, name):
        layers = QgsProject.instance().mapLayersByName(name)
        return layers[0] if layers else None

    def get_widget_settings(self, key, default=None):
        return self.settings.get(key, default)

    def set_widget_settings(self, key, value):
        self.settings[key] = value

    def set_basal_contacts(self, layer, unitname_field=None, use_z_coordinate=False):
        self.basal_contacts_calls.append((layer, unitname_field))

    def set_structural_orientations(self, *args, **kwargs):
        pass

    def logger(self, *args, **kwargs):
        pass


@pytest.fixture
def contacts_layer():
    start_app()
    layer = QgsVectorLayer("LineString?field=unitname:string", "basal_contacts", "memory")
    QgsProject.instance().addMapLayer(layer)
    yield layer
    QgsProject.instance().removeMapLayer(layer.id())


def test_the_guessed_contacts_layer_is_saved(contacts_layer):
    from loopstructural.gui.modelling.model_definition.stratigraphic_layers import (
        StratigraphicLayersWidget,
    )

    data_manager = _DataManager()
    StratigraphicLayersWidget(data_manager=data_manager)

    assert data_manager.basal_contacts_calls[-1] == (contacts_layer, 'unitname')
    settings = data_manager.settings['stratigraphic_layers_widget']
    assert settings['basal_layer'] == 'basal_contacts'
