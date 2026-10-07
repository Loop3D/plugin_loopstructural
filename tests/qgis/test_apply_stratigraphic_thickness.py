"""Tests for painting unit thickness from the stratigraphic column onto a layer."""

from unittest.mock import Mock

import pytest
from qgis.core import QgsFeature, QgsGraduatedSymbolRenderer, QgsProject, QgsVectorLayer

from loopstructural.main.data_manager import ModellingDataManager


@pytest.fixture
def data_manager():
    data_manager = ModellingDataManager(
        project=QgsProject.instance(), mapCanvas=Mock(), logger=Mock()
    )
    data_manager._stratigraphic_column.clear()
    data_manager._stratigraphic_column.add_unit(name='A', colour=None, thickness=10.0)
    data_manager._stratigraphic_column.add_unit(name='B', colour=None, thickness=25.0)
    data_manager._stratigraphic_column.add_unit(name='C', colour=None, thickness=25.0)
    return data_manager


@pytest.fixture
def geology_layer():
    layer = QgsVectorLayer("Polygon?crs=EPSG:28350&field=UNITNAME:string", "geology", "memory")
    features = []
    for name in ['A', 'B', 'C', 'unknown']:
        feature = QgsFeature(layer.fields())
        feature['UNITNAME'] = name
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    return layer


def test_thickness_is_written_for_each_unit(data_manager, geology_layer):
    assert data_manager.apply_stratigraphic_thickness_to_layer(geology_layer, 'UNITNAME')

    values = {f['UNITNAME']: f['strat_thickness'] for f in geology_layer.getFeatures()}
    assert values['A'] == pytest.approx(10.0)
    assert values['B'] == pytest.approx(25.0)
    assert values['C'] == pytest.approx(25.0)
    unknown = values['unknown']
    assert unknown is None or (hasattr(unknown, 'isNull') and unknown.isNull())


def test_layer_is_styled_with_one_class_per_thickness(data_manager, geology_layer):
    data_manager.apply_stratigraphic_thickness_to_layer(geology_layer, 'UNITNAME')

    renderer = geology_layer.renderer()
    assert isinstance(renderer, QgsGraduatedSymbolRenderer)
    assert renderer.classAttribute() == 'strat_thickness'
    assert [r.label() for r in renderer.ranges()] == ['10', '25']


def test_missing_unit_name_field_is_refused(data_manager, geology_layer):
    assert not data_manager.apply_stratigraphic_thickness_to_layer(geology_layer, 'NOPE')
