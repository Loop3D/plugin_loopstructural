import types

import pytest
from qgis.core import QgsFeature, QgsField, QgsFields, QgsVectorLayer, QgsWkbTypes
from qgis.PyQt.QtCore import QVariant
from qgis.testing import start_app


# Monkeypatch uic.loadUi to avoid needing the .ui file and to provide minimal widgets
class DummySignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self, *args, **kwargs):
        for cb in self._callbacks:
            cb(*args, **kwargs)


class DummyLayerComboBox:
    def __init__(self):
        self._layer = None
        self.layerChanged = DummySignal()

    def setFilters(self, *args, **kwargs):
        return None

    def currentLayer(self):
        return self._layer

    def setLayer(self, layer):
        self._layer = layer


class DummyFieldComboBox:
    def __init__(self):
        self._layer = None
        self._field = None

    def setLayer(self, layer):
        self._layer = layer

    def setField(self, field_name):
        self._field = field_name

    def currentField(self):
        return self._field


class DummyComboBox:
    def __init__(self):
        self._items = []
        self._current = None

    def addItems(self, items):
        self._items.extend(items)
        if self._current is None and items:
            self._current = items[0]

    def addItem(self, item):
        self._items.append(item)

    def currentText(self):
        return self._current

    def setCurrentText(self, txt):
        self._current = txt


class DummyCheckBox:
    def __init__(self):
        self._checked = False

    def setChecked(self, v):
        self._checked = bool(v)

    def isChecked(self):
        return self._checked


class DummyButton:
    def __init__(self):
        self.clicked = DummySignal()


@pytest.fixture(autouse=True)
def patch_uic_loadui(monkeypatch):
    import qgis.PyQt.uic as uic

    def fake_loadUi(ui_path, widget):
        # attach the minimal attributes the widget expects
        widget.geologyLayerComboBox = DummyLayerComboBox()
        widget.unitNameFieldComboBox = DummyFieldComboBox()
        widget.paintModeComboBox = DummyComboBox()
        widget.colorRampComboBox = DummyComboBox()
        widget.duplicateLayerCheckBox = DummyCheckBox()
        widget.runButton = DummyButton()

    monkeypatch.setattr('qgis.PyQt.uic.loadUi', fake_loadUi)
    yield


class DummyDataManager:
    def __init__(self, names):
        self._names = names
        self.stratigraphic_order = None

    def get_stratigraphic_unit_names(self):
        return self._names


class DummyDebug:
    def is_debug(self):
        return False

    def log_params(self, *args, **kwargs):
        return None


def make_geology_layer():
    # create a memory polygon layer with UNITNAME field and 3 polygons
    fields = QgsFields()
    fields.append(QgsField('UNITNAME', QVariant.String))

    uri = 'Polygon?crs=EPSG:4326'
    layer = QgsVectorLayer(uri, 'geology', 'memory')
    dp = layer.dataProvider()
    dp.addAttributes(list(fields))
    layer.updateFields()

    # add three simple square polygons as features (geometry not critical for paint)
    for name in ['Unit_A', 'Unit_B', 'Unit_C']:
        feat = QgsFeature()
        feat.setFields(layer.fields())
        feat.setAttributes([name])
        # set simple empty geometry
        feat.setGeometry(None)
        dp.addFeature(feat)

    layer.updateExtents()
    return layer


def test_widget_paint_stratigraphic_order(tmp_path):
    qgs = start_app()
    # import widget after patching loadUi
    from loopstructural.gui.map2loop_tools.paint_stratigraphic_order_widget import (
        PaintStratigraphicOrderWidget,
    )

    data_manager = DummyDataManager(['Unit_A', 'Unit_B', 'Unit_C'])
    debug = DummyDebug()

    widget = PaintStratigraphicOrderWidget(
        parent=None, data_manager=data_manager, debug_manager=debug
    )

    # Prepare a geology layer and set it on the combo box
    layer = make_geology_layer()
    widget.geologyLayerComboBox.setLayer(layer)
    # ensure field combo sees the layer
    widget.unitNameFieldComboBox.setLayer(layer)
    widget.unitNameFieldComboBox.setField('UNITNAME')

    # Run painter
    ok = widget._run_painter()
    assert ok is True

    # verify that the layer now has the 'strat_order' field
    field_names = [f.name() for f in layer.fields()]
    assert 'strat_order' in field_names

    # verify attributes were set (some may be None depending on implementation)
    vals = [f['strat_order'] for f in layer.getFeatures()]
    # at least one value should be not None (matching provided order)
    assert any(v is not None for v in vals)
