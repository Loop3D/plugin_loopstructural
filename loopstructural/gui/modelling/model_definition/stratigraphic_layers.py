import os

from qgis.core import QgsMapLayerProxyModel, QgsWkbTypes
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QComboBox, QWidget

from ...compatibility import configure_layer_combo
from ....main import layer_roles
from ....main.helpers import ColumnMatcher, get_layer_names


class StratigraphicLayersWidget(QWidget):
    def __init__(self, parent=None, data_manager=None):
        if data_manager is None:
            raise ValueError("data_manager must be provided")
        self.data_manager = data_manager
        self._loading = False
        super().__init__(parent)
        ui_path = os.path.join(os.path.dirname(__file__), "stratigraphic_layers.ui")
        uic.loadUi(ui_path, self)
        configure_layer_combo(
            self.basalContactsLayer,
            QgsMapLayerProxyModel.Filter.LineLayer | QgsMapLayerProxyModel.Filter.PointLayer,
            allow_empty=True,
        )
        # Structural data can only be points
        configure_layer_combo(self.structuralDataLayer, QgsMapLayerProxyModel.Filter.PointLayer)
        self._add_contacts_source_combo()
        self.basalContactsLayer.layerChanged.connect(self.onBasalContactsChanged)
        self.structuralDataLayer.layerChanged.connect(self.onStructuralDataLayerChanged)
        self.unitNameField.fieldChanged.connect(self.onUnitFieldChanged)
        self.orientationField.setLayer(self.structuralDataLayer.currentLayer())
        self.dipField.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.orientationField.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.structuralDataUnitName.setLayer(self.structuralDataLayer.currentLayer())
        self.structuralDataUnitName.fieldChanged.connect(self.onStructuralDataFieldChanged)
        self.orientationType.currentIndexChanged.connect(self.onOrientationTypeChanged)
        self.data_manager.set_basal_contacts_callback(self.set_basal_contacts)
        self.data_manager.set_structural_orientations_callback(self.set_orientations_layer)
        self.basal_contacts_use_z = False
        self.structural_points_use_z = False
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(
            lambda: self.enableBasalContactsZCheckBox(
                self.useBasalContactsZCoordinatesCheckBox.isChecked()
            )
        )
        self.useBasalContactsZCoordinatesCheckBox.stateChanged.connect(
            self.onStructuralDataFieldChanged
        )
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(
            lambda: self.enableStructuralPointsZCheckBox(
                self.useStructuralPointsZCoordinatesCheckBox.isChecked()
            )
        )
        self.useStructuralPointsZCoordinatesCheckBox.stateChanged.connect(
            self.onStructuralDataFieldChanged
        )
        self._guess_structure_layer()
        self._restore_selection()
        self._apply_contacts_source(self.data_manager.layer_roles.contacts_source)

    @property
    def _from_geology(self):
        return self.data_manager.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_GEOLOGY

    def _apply_contacts_source(self, source):
        """Set the filter, the labels and the selection of the first picker for a source.

        The geology source has one selection (the `geology` roles) and the layer
        source has another (the `basal_contacts` role). Each one is kept.
        """
        from_geology = source == layer_roles.CONTACTS_FROM_GEOLOGY
        self._loading = True
        try:
            if from_geology:
                configure_layer_combo(
                    self.basalContactsLayer,
                    QgsMapLayerProxyModel.Filter.PolygonLayer,
                    allow_empty=True,
                )
                self.groupBox_basalContacts.setTitle("Geology")
                self.basalContactsLabel.setText("Geology layer")
                self.label.setText("Unit name field")
                roles = self.data_manager.layer_roles
                layer = roles.get(layer_roles.GEOLOGY)
                field = roles.get(layer_roles.GEOLOGY_UNIT_FIELD)
            else:
                configure_layer_combo(
                    self.basalContactsLayer,
                    QgsMapLayerProxyModel.Filter.LineLayer | QgsMapLayerProxyModel.Filter.PointLayer,
                    allow_empty=True,
                )
                self.groupBox_basalContacts.setTitle("Basal contacts")
                self.basalContactsLabel.setText("Contacts layer")
                self.label.setText("Unit name field")
                layer = self.data_manager.layer_roles.get(layer_roles.BASAL_CONTACTS)
                field = (self.data_manager._basal_contacts or {}).get('unitname_field')
                if layer is None:
                    self._guess_basal_contacts()
                    layer = self.basalContactsLayer.currentLayer()
                    field = self.unitNameField.currentField() or field
            self.basalContactsLayer.setLayer(layer)
            self.unitNameField.setLayer(layer)
            if field:
                self.unitNameField.setField(field)
            self.useBasalContactsZCoordinatesCheckBox.setVisible(not from_geology)
            self.useZCoordinateLabel.setVisible(not from_geology)
        finally:
            self._loading = False

    def _add_contacts_source_combo(self):
        """Add the choice of where the basal contacts come from."""
        self.contactsSourceComboBox = QComboBox(self)
        self.contactsSourceComboBox.addItem(
            "Calculate from geology polygons", layer_roles.CONTACTS_FROM_GEOLOGY
        )
        self.contactsSourceComboBox.addItem("Use a contacts layer", layer_roles.CONTACTS_FROM_LAYER)
        self.contactsSourceComboBox.setToolTip(
            "Calculate from geology polygons: the plugin extracts the basal contacts from "
            "the geology layer and the stratigraphic column. The layer that it adds to the "
            "project is for display.\n"
            "Use a contacts layer: your own layer is an input. The plugin does not change it."
        )
        self.formLayout_basalContacts.insertRow(0, "Source", self.contactsSourceComboBox)
        self._show_contacts_source(self.data_manager.layer_roles.contacts_source)
        self.contactsSourceComboBox.currentIndexChanged.connect(self._on_contacts_source_selected)
        self.data_manager.layer_roles.attach(self._on_layer_role_changed)

    def _show_contacts_source(self, source):
        index = self.contactsSourceComboBox.findData(source)
        if index >= 0 and index != self.contactsSourceComboBox.currentIndex():
            self.contactsSourceComboBox.blockSignals(True)
            self.contactsSourceComboBox.setCurrentIndex(index)
            self.contactsSourceComboBox.blockSignals(False)

    def _on_contacts_source_selected(self, index):
        self.data_manager.layer_roles.contacts_source = self.contactsSourceComboBox.itemData(index)

    def _on_layer_role_changed(self, role, value):
        """Show a contacts source or a geology layer that something else set."""
        if role == 'contacts_source':
            self._show_contacts_source(value)
            self._apply_contacts_source(value)
        elif role in (layer_roles.GEOLOGY, layer_roles.GEOLOGY_UNIT_FIELD) and self._from_geology:
            self._apply_contacts_source(layer_roles.CONTACTS_FROM_GEOLOGY)
        elif role == layer_roles.BASAL_CONTACTS and not self._from_geology:
            self._apply_contacts_source(layer_roles.CONTACTS_FROM_LAYER)

    def enableBasalContactsZCheckBox(self, enable):
        self.useBasalContactsZCoordinatesCheckBox.setEnabled(enable)
        if enable:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(self.basal_contacts_use_z)
        else:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(False)

    def enableStructuralPointsZCheckBox(self, enable):
        self.useStructuralPointsZCoordinatesCheckBox.setEnabled(enable)
        if enable:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(self.structural_points_use_z)
        else:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(False)

    def set_basal_contacts(self, layer, unitname_field=None, use_z_coordinate=False):
        if self._from_geology:
            # The contacts layer is for display. The picker shows the geology layer.
            return
        self.basalContactsLayer.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Type.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())

                self.enableBasalContactsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.", log_level=2)
        else:
            self.enableBasalContactsZCheckBox(False)
        if unitname_field:
            self.unitNameField.setField(unitname_field)
        self.basal_contacts_use_z = use_z_coordinate
        self.useBasalContactsZCoordinatesCheckBox.setChecked(use_z_coordinate)

    def set_orientations_layer(
        self,
        layer,
        strike_field=None,
        dip_field=None,
        unitname_field=None,
        orientation_type=None,
        use_z_coordinate=False,
    ):
        self.structuralDataLayer.setLayer(layer)
        if layer is not None and layer.isValid():
            if layer.wkbType() != QgsWkbTypes.Type.Unknown:
                has_z = QgsWkbTypes.hasZ(layer.wkbType())
                self.enableStructuralPointsZCheckBox(has_z)
            else:
                self.data_manager.logger(message="Unknown geometry type.", level=2)
        else:
            self.enableStructuralPointsZCheckBox(False)
        if strike_field:
            self.orientationField.setField(strike_field)
        if dip_field:
            self.dipField.setField(dip_field)
        if unitname_field:
            self.structuralDataUnitName.setField(unitname_field)
        if orientation_type:
            index = self.orientationType.findText(orientation_type, Qt.MatchFlag.MatchFixedString)
            if index >= 0:
                self.orientationType.setCurrentIndex(index)
        if use_z_coordinate:
            self.structural_points_use_z = use_z_coordinate
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(use_z_coordinate)

    def _write_first_picker(self, layer, field):
        """Write the first picker to the role of the current source."""
        if self._from_geology:
            roles = self.data_manager.layer_roles
            roles.set(layer_roles.GEOLOGY, layer)
            roles.set(layer_roles.GEOLOGY_UNIT_FIELD, field or None)
        else:
            self.data_manager.set_basal_contacts(
                layer, field, use_z_coordinate=self.basal_contacts_use_z
            )

    def onBasalContactsChanged(self, layer):
        if self._loading:
            return
        self.unitNameField.setLayer(layer)
        self._write_first_picker(layer, self.unitNameField.currentField())
        self._persist_selection()

    def onOrientationTypeChanged(self, index):
        if index == 0:
            self.orientationLabel.setText("Strike")
        else:
            self.orientationLabel.setText("Dip Direction")

    def onStructuralDataLayerChanged(self, layer):
        self.orientationField.setLayer(layer)
        self.dipField.setLayer(layer)
        self.structuralDataUnitName.setLayer(layer)
        if self.dipField.currentField() is None or self.orientationField.currentField() is None:
            return
        self.data_manager.set_structural_orientations(
            layer,
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            use_z_coordinate=self.structural_points_use_z,
        )

    def onStructuralDataFieldChanged(self, field):
        if self.structuralDataLayer.currentLayer() is None:
            return
        if self.orientationField.currentField() is None or self.dipField.currentField() is None:
            return
        if self.structuralDataUnitName.currentField() is None:
            return

        self.data_manager.set_structural_orientations(
            self.structuralDataLayer.currentLayer(),
            self.orientationField.currentField(),
            self.dipField.currentField(),
            self.structuralDataUnitName.currentField(),
            self.orientationType.currentText(),
            use_z_coordinate=self.structural_points_use_z,
        )
        self._persist_selection()
        # self.updateDataManager()

    def onUnitFieldChanged(self, field):
        if self._loading:
            return
        self._write_first_picker(self.basalContactsLayer.currentLayer(), field)
        self._persist_selection()

    def _guess_basal_contacts(self):
        """Select a layer that is named like a contacts layer, in the layer source."""
        if not self.data_manager:
            return
        # Basal contacts
        basal_names = get_layer_names(self.basalContactsLayer)
        basal_matcher = ColumnMatcher(basal_names)
        basal_match = basal_matcher.find_match('BASAL_CONTACTS')
        if basal_match:
            layer = self.data_manager.find_layer_by_name(basal_match)
            if layer:
                self.basalContactsLayer.setLayer(layer)
                fields = [f.name() for f in layer.fields()]
                fmatcher = ColumnMatcher(fields)
                if unit_match := fmatcher.find_match('UNITNAME'):
                    self.unitNameField.setField(unit_match)

    def _guess_structure_layer(self):
        if not self.data_manager:
            return
        structural_names = get_layer_names(self.structuralDataLayer)
        structural_matcher = ColumnMatcher(structural_names)
        structural_match = structural_matcher.find_match(
            'STRUCTURE'
        ) or structural_matcher.find_match('ORIENTATION')
        if structural_match:
            layer = self.data_manager.find_layer_by_name(structural_match)
            if layer:
                self.structuralDataLayer.setLayer(layer)
                fields = [f.name() for f in layer.fields()]
                fmatcher = ColumnMatcher(fields)
                if strike_match := fmatcher.find_match('STRIKE') or fmatcher.find_match('DIPDIR'):
                    self.orientationField.setField(strike_match)
                if dip_match := fmatcher.find_match('DIP'):
                    self.dipField.setField(dip_match)
                if unit_match := fmatcher.find_match('UNITNAME'):
                    self.structuralDataUnitName.setField(unit_match)

    def _persist_selection(self):
        if not self.data_manager:
            return
        settings = dict(self.data_manager.get_widget_settings('stratigraphic_layers_widget', {}))
        if not self._from_geology:
            # In the geology source the first picker holds the geology layer. The
            # `geology` roles save it. Keep the contacts layer of the other source.
            settings['basal_layer'] = (
                self.basalContactsLayer.currentLayer().name()
                if self.basalContactsLayer.currentLayer()
                else None
            )
            settings['unit_name_field'] = self.unitNameField.currentField()
            settings['use_basal_z'] = self.useBasalContactsZCoordinatesCheckBox.isChecked()
        settings |= {
            'structural_layer': (
                self.structuralDataLayer.currentLayer().name()
                if self.structuralDataLayer.currentLayer()
                else None
            ),
            'orientation_field': self.orientationField.currentField(),
            'dip_field': self.dipField.currentField(),
            'structural_unit_field': self.structuralDataUnitName.currentField(),
            'orientation_type': self.orientationType.currentText(),
            'use_structural_z': self.useStructuralPointsZCoordinatesCheckBox.isChecked(),
        }
        self.data_manager.set_widget_settings('stratigraphic_layers_widget', settings)

    def _restore_selection(self):
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('stratigraphic_layers_widget', {})
        if not settings:
            return
        # The first picker of the geology source comes from the `geology` roles
        if not self._from_geology:
            if layer_name := settings.get('basal_layer'):
                layer = self.data_manager.find_layer_by_name(layer_name)
                if layer:
                    self.basalContactsLayer.setLayer(layer)
            if field := settings.get('unit_name_field'):
                self.unitNameField.setField(field)
        if layer_name := settings.get('structural_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.structuralDataLayer.setLayer(layer)
        if field := settings.get('orientation_field'):
            self.orientationField.setField(field)
        if field := settings.get('dip_field'):
            self.dipField.setField(field)
        if field := settings.get('structural_unit_field'):
            self.structuralDataUnitName.setField(field)
        if 'orientation_type' in settings:
            idx = self.orientationType.findText(
                settings['orientation_type'], Qt.MatchFlag.MatchFixedString
            )
            if idx >= 0:
                self.orientationType.setCurrentIndex(idx)
        if 'use_basal_z' in settings and not self._from_geology:
            self.useBasalContactsZCoordinatesCheckBox.setChecked(settings['use_basal_z'])
        if 'use_structural_z' in settings:
            self.useStructuralPointsZCoordinatesCheckBox.setChecked(settings['use_structural_z'])
