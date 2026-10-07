"""The "Calculate topology" button of step 3 follows the fault layer."""

from unittest.mock import Mock

import pytest
from qgis.core import QgsProject, QgsVectorLayer

from loopstructural.gui.modelling.steps.pages import FaultsStep
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager


@pytest.fixture
def page():
    project = QgsProject.instance()
    model_manager = GeologicalModelManager()
    data_manager = ModellingDataManager(
        project=project, mapCanvas=Mock(), logger=Mock()
    )
    data_manager.set_model_manager(model_manager)
    return FaultsStep(None, data_manager=data_manager, model_manager=model_manager)


def test_button_is_disabled_without_a_fault_layer(page):
    assert not page.topology_button.isEnabled()
    assert 'fault layer' in page.topology_button.toolTip()


def test_button_is_enabled_with_layer_and_name_field(page):
    layer = QgsVectorLayer('LineString?field=name:string', 'faults', 'memory')
    QgsProject.instance().addMapLayer(layer)
    page.data_manager.set_fault_trace_layer(layer, fault_name_field='name')
    page.update_topology_button()
    assert page.topology_button.isEnabled()
    page.data_manager.set_fault_trace_layer(layer, fault_name_field=None)
    page.update_topology_button()
    assert not page.topology_button.isEnabled()
