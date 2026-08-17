from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumnElementType
from qgis.core import QgsMapLayerProxyModel, QgsStyle
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.compatibility import configure_layer_combo
from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget
from loopstructural.main.helpers import ColumnMatcher, get_layer_names

from .stratigraphic_unit import StratigraphicUnitWidget


class StratColumnWidget(QWidget):
    """Widget that controls building the stratigraphic column.

    Parameters
    ----------
    parent : QWidget, optional
        Parent widget, by default None.
    data_manager : object
        Data manager instance used to manage the stratigraphic column. Must be provided.

    Notes
    -----
    The widget updates its display based on the data_manager's stratigraphic column
    and registers a callback via data_manager.set_stratigraphic_column_callback.

    This widget uses efficient incremental updates rather than full rebuilds when possible.
    """

    def __init__(self, parent=None, data_manager=None):
        super().__init__()
        layout = QVBoxLayout(self)
        if data_manager is None:
            raise ValueError("Data manager must be provided.")
        self.data_manager = data_manager

        # Cache to track current widgets and their UUIDs for efficient updates
        self._widget_cache = {}  # Maps UUID -> (widget, list_item)

        # Flag to prevent recursive/reentrant callbacks during updates
        self._updating = False

        # State tracked while a row is being dragged by its grip handle
        self._drag_widget = None
        self._drag_target_row = None
        self._drop_indicator_row = None

        # Cache of exact unit-name values found in the selected units layer's
        # field, refreshed by _revalidate_unit_names(). None means no
        # layer/field is selected, so the name-match warning is skipped.
        self._known_unit_names = None

        # Main list widget
        self.unitList = QListWidget()
        self.unitList.setDragDropMode(QAbstractItemView.InternalMove)
        self.unitList.model().rowsMoved.connect(self.update_order)
        layout.addWidget(self.unitList)

        # Add unit button
        addUnitButton = QPushButton("Add Unit")
        addUnitButton.clicked.connect(self.add_unit)
        layout.addWidget(addUnitButton)

        # Add unconformity button
        addUnconformityButton = QPushButton("Add Unconformity")
        addUnconformityButton.clicked.connect(self.add_unconformity)
        layout.addWidget(addUnconformityButton)

        # add init from basal contacts button
        initFromBasalContactsButton = QPushButton("Initialise from map")
        initFromBasalContactsButton.clicked.connect(
            self.init_stratigraphic_column_from_basal_contacts
        )
        layout.addWidget(initFromBasalContactsButton)

        # Layer/field pickers for pushing colours back onto a map layer
        layerRow = QHBoxLayout()
        self.unitsLayerComboBox = QgsMapLayerComboBox()
        configure_layer_combo(
            self.unitsLayerComboBox, QgsMapLayerProxyModel.PolygonLayer, allow_empty=True
        )
        self.unitsLayerComboBox.setCurrentIndex(-1)
        self.unitsLayerFieldComboBox = QgsFieldComboBox()
        self.unitsLayerComboBox.layerChanged.connect(self._on_units_layer_changed)
        self.unitsLayerFieldComboBox.fieldChanged.connect(self._on_units_field_changed)
        layerRow.addWidget(self.unitsLayerComboBox)
        layerRow.addWidget(self.unitsLayerFieldComboBox)
        layout.addLayout(layerRow)

        # add apply colours to map button
        applyColoursButton = QPushButton("Apply Colours to Map Layer")
        applyColoursButton.setToolTip(
            "Push the colours defined in the stratigraphic column onto the "
            "selected layer above as a categorized renderer."
        )
        applyColoursButton.clicked.connect(self.apply_colours_to_layer)
        layout.addWidget(applyColoursButton)

        # Colour ramp picker + apply stratigraphic age button
        ageRow = QHBoxLayout()
        ageRow.addWidget(QLabel("Colour ramp:"))
        self.strat_ageColorRampComboBox = QComboBox()
        ramp_names = sorted(QgsStyle().defaultStyle().colorRampNames())
        self.strat_ageColorRampComboBox.addItems(ramp_names)
        default_ramp_index = self.strat_ageColorRampComboBox.findText('Viridis')
        if default_ramp_index >= 0:
            self.strat_ageColorRampComboBox.setCurrentIndex(default_ramp_index)
        ageRow.addWidget(self.strat_ageColorRampComboBox)
        layout.addLayout(ageRow)

        applyAgeButton = QPushButton("Apply Stratigraphic Age to Map Layer")
        applyAgeButton.setToolTip(
            "Write a 'strat_order' field (0 = first unit in the column) onto "
            "the selected layer above and style it with a graduated colour ramp."
        )
        applyAgeButton.clicked.connect(self.apply_age_to_layer)
        layout.addWidget(applyAgeButton)

        self._guess_units_layer()
        self._restore_units_layer_selection()
        self._known_unit_names = self._get_known_unit_names()

        clearButton = QPushButton("Clear Stratigraphic Column")
        clearButton.clicked.connect(self.clearColumn)
        layout.addWidget(clearButton)
        # Update display from data manager
        self.update_display()
        self.data_manager.set_stratigraphic_column_callback(self.update_display)

    def clearColumn(self):
        """Clear the stratigraphic column."""
        # Use the data manager's clear method to ensure callback is triggered
        # This will notify all listening widgets (including this one and others)
        if self.data_manager:
            self.data_manager._stratigraphic_column.clear()
            # Trigger callback to notify all listeners
            if self.data_manager.stratigraphic_column_callback:
                self.data_manager.stratigraphic_column_callback()
        else:
            # Fallback: clear locally if no data manager
            self.unitList.clear()
            self._widget_cache.clear()
            print("Error: Data manager is not initialized.")

    def update_display(self):
        """Update the widget display with efficient incremental updates.

        Instead of rebuilding the entire display, this method:
        1. Identifies items that were added/removed/reordered
        2. Only updates what changed
        3. Falls back to full rebuild only when necessary

        This method is protected against recursive/reentrant calls during active updates.
        """
        # Prevent reentrant calls during updates
        if self._updating:
            return

        self._updating = True
        try:
            # Check if the list widget is still valid
            try:
                if not self.data_manager or not self.data_manager._stratigraphic_column:
                    self.unitList.clear()
                    self._widget_cache.clear()
                    return
            except RuntimeError:
                # Widget was deleted
                return

            current_order = self.data_manager._stratigraphic_column.order
            current_uuids = [unit.uuid for unit in current_order]
            cached_uuids = list(self._widget_cache.keys())

            # Check if the order and content match
            if current_uuids == cached_uuids:
                # No changes in order or content, just update data if needed
                for unit in current_order:
                    if unit.uuid in self._widget_cache:
                        widget, _ = self._widget_cache[unit.uuid]
                        # Update widget data without rebuilding
                        if hasattr(widget, 'setData'):
                            widget.setData(unit.to_dict())
                return

            # If order/content differs, do a full rebuild
            # but only as a last resort
            self._full_rebuild_display(current_order)
        finally:
            self._updating = False

    def _full_rebuild_display(self, current_order):
        """Perform a full rebuild of the display (called only when necessary).

        Parameters
        ----------
        current_order : list
            The current order of elements in the stratigraphic column
        """
        # Check if the list widget is still valid (could be deleted in some cases)
        try:
            # Clear the list and cache
            self.unitList.clear()
            self._widget_cache.clear()
        except RuntimeError:
            # Widget was deleted, can't rebuild
            return

        # Rebuild from scratch
        for unit in current_order:
            if unit.element_type == StratigraphicColumnElementType.UNIT:
                self.add_unit(unit_data=unit.to_dict(), create_new=False)
            elif unit.element_type == StratigraphicColumnElementType.UNCONFORMITY:
                self.add_unconformity(unconformity_data=unit.to_dict(), create_new=False)

    def init_stratigraphic_column_from_basal_contacts(self):
        if self.data_manager:
            self.data_manager.init_stratigraphic_column_from_basal_contacts()
            self.update_display()
        else:
            print("Error: Data manager is not initialized.")

    def _guess_units_layer(self):
        """Attempt to auto-select the geological units layer and unit name field."""
        layer_names = get_layer_names(self.unitsLayerComboBox)
        matcher = ColumnMatcher(layer_names)
        layer_match = matcher.find_match('GEOLOGY')
        if layer_match and self.data_manager:
            layer = self.data_manager.find_layer_by_name(layer_match)
            if layer:
                self.unitsLayerComboBox.setLayer(layer)

    def _restore_units_layer_selection(self):
        """Restore a previously persisted units layer/field selection."""
        if not self.data_manager:
            return
        settings = self.data_manager.get_widget_settings('stratigraphic_column_widget', {})
        if not settings:
            return
        if layer_name := settings.get('units_layer'):
            layer = self.data_manager.find_layer_by_name(layer_name)
            if layer:
                self.unitsLayerComboBox.setLayer(layer)
        if field := settings.get('units_layer_field'):
            self.unitsLayerFieldComboBox.setField(field)

    def _persist_units_layer_selection(self):
        """Persist the current units layer/field selection."""
        if not self.data_manager:
            return
        layer = self.unitsLayerComboBox.currentLayer()
        self.data_manager.set_widget_settings(
            'stratigraphic_column_widget',
            {
                'units_layer': layer.name() if layer else None,
                'units_layer_field': self.unitsLayerFieldComboBox.currentField(),
            },
        )

    def _on_units_field_changed(self, _field_name):
        """Persist and re-validate when the unit-name field selection changes."""
        self._persist_units_layer_selection()
        self._revalidate_unit_names()

    def _on_units_layer_changed(self, layer):
        """Update the field combo box when the units layer changes."""
        self.unitsLayerFieldComboBox.setLayer(layer)
        if layer:
            fields = [field.name() for field in layer.fields()]
            matcher = ColumnMatcher(fields)
            if unit_match := matcher.find_match('UNITNAME'):
                self.unitsLayerFieldComboBox.setField(unit_match)
        self._persist_units_layer_selection()
        self._revalidate_unit_names()

    def _get_known_unit_names(self):
        """Return the set of exact unit-name values in the selected geology layer/field.

        Returns None if no units layer or unit-name field is selected, which
        means the name-match warning on each unit row should be skipped.
        """
        layer = self.unitsLayerComboBox.currentLayer()
        field_name = self.unitsLayerFieldComboBox.currentField()
        if layer is None or not field_name:
            return None
        if layer.fields().indexFromName(field_name) < 0:
            return None
        names = set()
        for feature in layer.getFeatures():
            value = feature[field_name]
            if value is None:
                continue
            text = str(value).strip()
            if text:
                names.add(text)
        return names

    def _revalidate_unit_names(self):
        """Refresh the known-names cache and re-check every unit row against it."""
        self._known_unit_names = self._get_known_unit_names()
        for widget, _ in self._widget_cache.values():
            if hasattr(widget, 'set_known_unit_names'):
                widget.set_known_unit_names(self._known_unit_names)

    def apply_colours_to_layer(self):
        """Push the stratigraphic column's colours onto the selected units layer."""
        if not self.data_manager:
            print("Error: Data manager is not initialized.")
            return
        layer = self.unitsLayerComboBox.currentLayer()
        field_name = self.unitsLayerFieldComboBox.currentField()
        if layer is None or not field_name:
            QMessageBox.warning(
                self,
                "Apply Colours to Map Layer",
                "Please select a units layer and unit name field above.",
            )
            return
        applied = self.data_manager.apply_stratigraphic_colours_to_layer(layer, field_name)
        if applied:
            QMessageBox.information(
                self,
                "Apply Colours to Map Layer",
                f"Applied stratigraphic column colours to layer '{layer.name()}'.",
            )
        else:
            QMessageBox.warning(
                self,
                "Apply Colours to Map Layer",
                "Could not apply colours. The stratigraphic column may have no units.",
            )

    def apply_age_to_layer(self):
        """Write the stratigraphic order onto the selected units layer and style it by a graduated ramp."""
        if not self.data_manager:
            print("Error: Data manager is not initialized.")
            return
        layer = self.unitsLayerComboBox.currentLayer()
        field_name = self.unitsLayerFieldComboBox.currentField()
        if layer is None or not field_name:
            QMessageBox.warning(
                self,
                "Apply Stratigraphic Age to Map Layer",
                "Please select a units layer and unit name field above.",
            )
            return
        ramp_name = self.strat_ageColorRampComboBox.currentText()
        applied = self.data_manager.apply_stratigraphic_age_to_layer(
            layer, field_name, ramp_name=ramp_name
        )
        if applied:
            QMessageBox.information(
                self,
                "Apply Stratigraphic Age to Map Layer",
                f"Applied stratigraphic age and graduated styling to layer '{layer.name()}'.",
            )
        else:
            QMessageBox.warning(
                self,
                "Apply Stratigraphic Age to Map Layer",
                "Could not apply stratigraphic age. The stratigraphic column may have no "
                "units, or no features matched a stratigraphic unit.",
            )

    def add_unit(self, *, unit_data=None, create_new=True):
        if unit_data is None:
            unit_data = {'type': 'unit', 'name': ''}
        if create_new:
            unit = self.data_manager.add_to_stratigraphic_column(unit_data)
            unit_data['uuid'] = unit.uuid
        else:
            if unit_data['uuid'] is not None or unit_data['uuid'] != '':

                unit = self.data_manager._stratigraphic_column.get_element_by_uuid(
                    unit_data['uuid']
                )

        # Check if widget already exists in cache (avoid duplicates during rebuild)
        if unit_data['uuid'] in self._widget_cache:
            widget, _ = self._widget_cache[unit_data['uuid']]
            # Just update the data, don't recreate the widget
            if hasattr(widget, 'setData'):
                widget.setData(unit_data)
            return

        unit_data.pop('type', None)  # Remove type if present
        unit_data.pop('id', None)
        for k in list(unit_data.keys()):
            if unit_data[k] is None:
                unit_data.pop(k)
        unit_widget = StratigraphicUnitWidget(**unit_data)
        unit_widget.deleteRequested.connect(self.delete_unit)  # Connect delete signal
        unit_widget.nameChanged.connect(
            lambda: self.update_element(unit_widget)
        )  # Connect name change signal

        unit_widget.thicknessChanged.connect(
            lambda: self.update_element(unit_widget)
        )  # Connect thickness change signal

        unit_widget.set_thickness(unit_data.get('thickness', 0.0))  # Set initial thickness
        unit_widget.colourChanged.connect(
            lambda: self.update_element(unit_widget)
        )  # Connect colour change signal
        unit_widget.dragHandlePressed.connect(lambda: self._on_drag_start(unit_widget))
        unit_widget.dragHandleMoved.connect(lambda pos: self._on_drag_move(unit_widget, pos))
        unit_widget.dragHandleReleased.connect(lambda: self._on_drag_end(unit_widget))
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)
        unit_widget.setData(unit_data)  # Set data for the unit widget
        unit_widget.set_known_unit_names(self._known_unit_names)

        # Cache the widget for efficient updates
        self._widget_cache[unit_data['uuid']] = (unit_widget, item)

    def add_unconformity(self, *, unconformity_data=None, create_new=True):
        if unconformity_data is None:
            unconformity_data = {'type': 'unconformity', 'unconformity_type': 'erode'}
        if create_new:
            unconformity = self.data_manager.add_to_stratigraphic_column(unconformity_data)
        else:
            unconformity = self.data_manager._stratigraphic_column.get_element_by_uuid(
                unconformity_data['uuid']
            )

        # Check if widget already exists in cache (avoid duplicates during rebuild)
        if unconformity.uuid in self._widget_cache:
            widget, _ = self._widget_cache[unconformity.uuid]
            # Just update the data, don't recreate the widget
            if hasattr(widget, 'setData'):
                widget.setData(unconformity_data)
            return

        unconformity_widget = UnconformityWidget(uuid=unconformity.uuid)
        unconformity_widget.deleteRequested.connect(self.delete_unit)
        unconformity_widget.dragHandlePressed.connect(
            lambda: self._on_drag_start(unconformity_widget)
        )
        unconformity_widget.dragHandleMoved.connect(
            lambda pos: self._on_drag_move(unconformity_widget, pos)
        )
        unconformity_widget.dragHandleReleased.connect(
            lambda: self._on_drag_end(unconformity_widget)
        )
        item = QListWidgetItem()
        item.setSizeHint(unconformity_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unconformity_widget)

        # Cache the widget for efficient updates
        self._widget_cache[unconformity.uuid] = (unconformity_widget, item)

    def delete_unit(self, unit_widget):
        for i in range(self.unitList.count()):
            item = self.unitList.item(i)
            if self.unitList.itemWidget(item) == unit_widget:
                self.unitList.takeItem(i)
                break

        # Update data manager and cache
        if self.data_manager:
            self.data_manager.remove_from_stratigraphic_column(unit_widget.uuid)

        # Remove from cache
        if unit_widget.uuid in self._widget_cache:
            del self._widget_cache[unit_widget.uuid]

    def _on_drag_start(self, widget):
        """Begin a reorder drag started from a row's grip handle."""
        self._drag_widget = widget
        self._drag_target_row = None

    def _on_drag_move(self, widget, global_pos):
        """Track the row currently under the cursor and highlight it as the drop target."""
        if self._drag_widget is not widget:
            return
        viewport = self.unitList.viewport()
        local_pos = viewport.mapFromGlobal(global_pos)
        index = self.unitList.indexAt(local_pos)
        if index.isValid():
            target_row = index.row()
        elif local_pos.y() < 0:
            target_row = 0
        else:
            target_row = self.unitList.count() - 1
        self._drag_target_row = target_row
        self._set_drop_indicator(target_row)

    def _on_drag_end(self, widget):
        """Finish a reorder drag, applying the move if the target row changed."""
        if self._drag_widget is not widget:
            return
        target_row = self._drag_target_row
        self._drag_widget = None
        self._drag_target_row = None
        self._set_drop_indicator(None)

        if target_row is None or not self.data_manager:
            return

        ordered_uuids = [
            self.unitList.itemWidget(self.unitList.item(i)).uuid
            for i in range(self.unitList.count())
        ]
        try:
            current_row = ordered_uuids.index(widget.uuid)
        except ValueError:
            return
        if current_row == target_row:
            return
        ordered_uuids.pop(current_row)
        ordered_uuids.insert(target_row, widget.uuid)
        self.data_manager.update_stratigraphic_column_order(ordered_uuids)

    def _set_drop_indicator(self, row):
        """Highlight the row a drag would drop onto, clearing any previous highlight."""
        if self._drop_indicator_row == row:
            return
        if self._drop_indicator_row is not None:
            item = self.unitList.item(self._drop_indicator_row)
            if item:
                previous_widget = self.unitList.itemWidget(item)
                if previous_widget:
                    previous_widget.setStyleSheet("")
        self._drop_indicator_row = row
        if row is not None:
            item = self.unitList.item(row)
            if item:
                target_widget = self.unitList.itemWidget(item)
                if target_widget:
                    target_widget.setStyleSheet("border-top: 3px solid #2a82da;")

    def update_order(self, parent, start, end, destination, row):
        """Update the data manager when the order of items changes."""
        if self.data_manager:
            ordered_uuids = []
            for i in range(self.unitList.count()):
                item = self.unitList.item(i)
                widget = self.unitList.itemWidget(item)
                if widget:
                    ordered_uuids.append(widget.uuid)
                else:
                    print(f"Warning: Item at index {i} has no widget associated with it.")
            self.data_manager.update_stratigraphic_column_order(ordered_uuids)

    def update_element(self, unit_widget):
        """Update the data manager with the changes made in the unit widget.

        After updating the element, triggers the callback to notify all listeners
        (including other widgets) that the stratigraphic column has changed.
        """
        if self.data_manager:
            unit_data = unit_widget.getData()
            self.data_manager._stratigraphic_column.update_element(unit_data)
            # Trigger callback to notify all listeners of the change
            if self.data_manager.stratigraphic_column_callback:
                self.data_manager.stratigraphic_column_callback()
