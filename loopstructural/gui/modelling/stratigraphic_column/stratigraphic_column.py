from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumnElementType
from qgis.core import QgsApplication, QgsExpression, QgsMapLayerProxyModel, QgsStyle
from qgis.gui import QgsCollapsibleGroupBox, QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QIcon
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.__about__ import DIR_PLUGIN_ROOT
from loopstructural.gui.compatibility import configure_layer_combo
from loopstructural.gui.messages import push_success
from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget
from loopstructural.main import derived_data, layer_roles
from loopstructural.main.helpers import ColumnMatcher, get_layer_names

from .init_from_field_dialog import InitFromLayerFieldDialog
from .stratigraphic_unit import StratigraphicUnitWidget


# The values of the "Style by" combo
STYLE_COLOUR = 'colour'
STYLE_ORDER = 'order'
STYLE_THICKNESS = 'thickness'


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

        # True while the pickers follow a change of the shared geology role,
        # so that the change is not written back
        self._syncing_roles = False
        # The hidden tool widget that an Update button runs
        self._update_widget = None

        # The layer whose features were selected to highlight the selected
        # unit on the map, so the selection can be cleared later.
        self._highlighted_layer = None

        # The geology layer and its unit name field. The layer is shared with
        # the map2loop tools, and the "Style map layer" group writes to it.
        layout.addWidget(self._build_geology_group())

        layout.addLayout(self._build_actions_row())

        # Main list widget, with the direction of the column above and below it
        self.unitList = QListWidget()
        self.unitList.setMinimumHeight(120)
        self.unitList.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.unitList.model().rowsMoved.connect(self.update_order)
        self.unitList.itemSelectionChanged.connect(self.highlight_selected_unit)
        self._add_empty_list_text()
        layout.addWidget(QLabel("Youngest"))
        layout.addWidget(self.unitList, 1)
        layout.addWidget(QLabel("Oldest"))

        layout.addWidget(self._build_style_group())

        self._add_derived_data_panel(layout)

        self._guess_units_layer()
        self._restore_units_layer_selection()
        self._sync_units_layer_from_roles()
        self._known_unit_names = self._get_known_unit_names()
        self.data_manager.layer_roles.attach(self._on_layer_role_changed)

        # Update display from data manager
        self.update_display()
        self.data_manager.set_stratigraphic_column_callback(self.update_display)
        self.data_manager._fault_topology.attach(self._on_fault_topology_changed)

    def _on_fault_topology_changed(self, observable, event, *args, **kwargs):
        """Refresh the fault-name picker of each unconformity row when faults
        are added or removed (e.g. a new fault trace layer is selected).
        """
        fault_names = self._get_available_fault_names()
        for widget, _ in list(self._widget_cache.values()):
            if isinstance(widget, UnconformityWidget):
                try:
                    widget.set_available_faults(fault_names)
                except RuntimeError:
                    # Widget was deleted
                    pass

    # Words for the inputs that changed, in the message of an out-of-date result
    _INPUT_WORDS = {
        'unit_order': 'the order of the units',
        'geology': 'the geology layer',
        'unit_field': 'the unit name field',
        'faults': 'the faults layer',
        'ignore_units': 'the ignored units',
        'override_units': 'the basal override units',
        'contacts': 'the basal contacts settings',
        'calculator_type': 'the calculator type',
        'structure': 'the structure layer',
        'cross_sections': 'the cross-sections layer',
        'thicknesses': 'a unit thickness',
    }

    def _add_derived_data_panel(self, layout):
        """Add the list of the derived results that are out of date.

        Each result has a line of text and an Update button. The panel is
        hidden when all results are current. The column does not calculate
        again after each change, because the extraction is slow and the user
        often moves many rows.
        """
        self.derivedDataPanel = QWidget(self)
        panel_layout = QVBoxLayout(self.derivedDataPanel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        self._derived_rows = {}
        for name in (
            derived_data.BASAL_CONTACTS,
            derived_data.THICKNESS,
            derived_data.STYLED_FIELDS,
        ):
            row = QWidget(self.derivedDataPanel)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(row)
            label.setWordWrap(True)
            button = QPushButton("Update", row)
            button.setIcon(QgsApplication.getThemeIcon("mActionRefresh.svg"))
            button.clicked.connect(lambda _checked=False, n=name: self._update_derived(n))
            row_layout.addWidget(label, 1)
            row_layout.addWidget(button)
            panel_layout.addWidget(row)
            self._derived_rows[name] = (row, label, button)
        layout.addWidget(self.derivedDataPanel)
        self.data_manager.derived.attach(self._on_derived_status_changed)
        self._refresh_derived_panel()

    def _on_derived_status_changed(self, name, status):
        try:
            self._refresh_derived_panel()
        except RuntimeError:
            # the widget was deleted
            pass

    def _refresh_derived_panel(self):
        """Show a line for each result that is out of date."""
        derived = self.data_manager.derived
        any_visible = False
        for name, (row, label, _button) in self._derived_rows.items():
            visible = derived.is_out_of_date(name)
            # With "Use a contacts layer", the contacts are an input of the
            # user and not a result of the plugin.
            if (
                name == derived_data.BASAL_CONTACTS
                and self.data_manager.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_LAYER
            ):
                visible = False
            row.setVisible(visible)
            if visible:
                any_visible = True
                words = [
                    self._INPUT_WORDS.get(key, key.replace('_', ' '))
                    for key in derived.changed_inputs(name)
                ]
                reason = f" ({', '.join(words)} changed)" if words else ""
                label.setText(f"{derived_data.DESCRIPTIONS[name]} are out of date{reason}.")
        self.derivedDataPanel.setVisible(any_visible)

    def _update_derived(self, name):
        """Calculate an out-of-date result again with the settings of the project."""
        if self._update_widget is not None:
            # a calculation is running
            return
        if name == derived_data.STYLED_FIELDS:
            self._update_styled_fields()
            return
        if name == derived_data.BASAL_CONTACTS:
            from loopstructural.gui.map2loop_tools.basal_contacts_widget import (
                BasalContactsWidget as tool_class,
            )

            run_method = '_run_extractor'
        else:
            from loopstructural.gui.map2loop_tools.thickness_calculator_widget import (
                ThicknessCalculatorWidget as tool_class,
            )

            run_method = '_run_calculator'
        # The tool widget takes its settings from the layer roles and from the
        # last run. It is not shown. Its progress dialog is shown.
        widget = tool_class(
            self, data_manager=self.data_manager, debug_manager=self.data_manager.debug_manager
        )
        widget.hide()
        widget.task_succeeded.connect(self._finish_update)
        widget.task_failed.connect(self._finish_update)
        self._update_widget = widget
        self._set_update_buttons_enabled(False)
        if getattr(widget, run_method)() is False:
            # The tool did not start, for example no geology layer is selected.
            # It showed the reason.
            self._finish_update()

    def _update_styled_fields(self):
        """Write the order of the column again to the layer that was styled."""
        detail = self.data_manager.derived.detail(derived_data.STYLED_FIELDS)
        layer = self.data_manager.find_layer_by_name(detail.get('layer'))
        field = detail.get('field') or self.data_manager.layer_roles.get(
            layer_roles.GEOLOGY_UNIT_FIELD
        )
        if layer is None or not field:
            QMessageBox.warning(
                self,
                "Update Map Layer Fields",
                "The layer that has the stratigraphic order fields is not in the project. "
                "Use 'Apply Stratigraphic Age to Map Layer' to write them again.",
            )
            return
        if not self.data_manager.refresh_stratigraphic_order_field(layer, field):
            QMessageBox.warning(
                self,
                "Update Map Layer Fields",
                f"Could not write the stratigraphic order to layer '{layer.name()}'.",
            )

    def _finish_update(self):
        widget, self._update_widget = self._update_widget, None
        if widget is not None:
            widget.deleteLater()
        self._set_update_buttons_enabled(True)

    def _set_update_buttons_enabled(self, enabled):
        for _row, _label, button in self._derived_rows.values():
            button.setEnabled(enabled)

    def _build_geology_group(self):
        """Build the group with the geology layer, the unit name field and a
        summary of the unit names that have no match in the layer."""
        group = QGroupBox("Geology layer", self)
        form = QFormLayout(group)
        self.unitsLayerComboBox = QgsMapLayerComboBox()
        configure_layer_combo(
            self.unitsLayerComboBox, QgsMapLayerProxyModel.Filter.PolygonLayer, allow_empty=True
        )
        self.unitsLayerComboBox.setCurrentIndex(-1)
        self.unitsLayerComboBox.setToolTip("The polygon layer that has the geological units.")
        self.unitsLayerFieldComboBox = QgsFieldComboBox()
        self.unitsLayerFieldComboBox.setToolTip("The field that has the name of each unit.")
        self.unitsLayerComboBox.layerChanged.connect(self._on_units_layer_changed)
        self.unitsLayerFieldComboBox.fieldChanged.connect(self._on_units_field_changed)
        form.addRow("Layer", self.unitsLayerComboBox)
        form.addRow("Unit name field", self.unitsLayerFieldComboBox)
        self.unitNamesSummaryLabel = QLabel()
        self.unitNamesSummaryLabel.setWordWrap(True)
        form.addRow(self.unitNamesSummaryLabel)
        return group

    def _build_actions_row(self):
        """Build the row of buttons that change the column."""
        addUnitButton = QPushButton("+ Unit", self)
        addUnitButton.setToolTip("Add a unit to the top of the column.")
        addUnitButton.clicked.connect(lambda _checked=False: self.add_unit())

        addUnconformityButton = QPushButton("+ Unconformity", self)
        addUnconformityButton.setIcon(
            QIcon(str(DIR_PLUGIN_ROOT / "resources" / "images" / "unconformity.svg"))
        )
        addUnconformityButton.setToolTip("Add an unconformity to the top of the column.")
        addUnconformityButton.clicked.connect(lambda _checked=False: self.add_unconformity())

        buildMenu = QMenu(self)
        buildMenu.addAction(
            QgsApplication.getThemeIcon("mActionSharingImport.svg"),
            "From the basal contacts of the map",
            self.init_stratigraphic_column_from_basal_contacts,
        ).setToolTip("Add the units in the order that the basal contacts give.")
        buildMenu.addAction(
            QgsApplication.getThemeIcon("mIconFieldText.svg"),
            "From a layer field...",
            self.init_stratigraphic_column_from_layer_field,
        ).setToolTip(
            "Pick a polygon layer and a field, and add a unit for each unique value "
            "found in that field."
        )
        buildButton = QToolButton(self)
        buildButton.setText("Build column")
        buildButton.setToolTip("Add units to the column from the map data.")
        buildButton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        buildButton.setIcon(QgsApplication.getThemeIcon("mActionSharingImport.svg"))
        buildButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        buildButton.setMenu(buildMenu)

        moreMenu = QMenu(self)
        moreMenu.addAction(
            QgsApplication.getThemeIcon("mActionReverseLine.svg"),
            "Reverse the column",
            self.reverseColumn,
        ).setToolTip("Flip the order of the column so the youngest unit becomes the oldest.")
        moreMenu.addAction(
            QgsApplication.getThemeIcon("mActionDeleteSelected.svg"),
            "Clear the column...",
            self.clearColumn,
        )
        moreButton = QToolButton(self)
        moreButton.setIcon(QgsApplication.getThemeIcon("mActionOptions.svg"))
        moreButton.setToolTip("More actions")
        moreButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        moreButton.setMenu(moreMenu)

        row = QHBoxLayout()
        row.addWidget(addUnitButton)
        row.addWidget(addUnconformityButton)
        row.addWidget(buildButton)
        row.addStretch(1)
        row.addWidget(moreButton)
        return row

    def _build_style_group(self):
        """Build the group that styles the geology layer by the column."""
        group = QgsCollapsibleGroupBox("Style map layer", self)
        form = QFormLayout(group)
        self.styleByComboBox = QComboBox()
        self.styleByComboBox.addItem("Unit colour", STYLE_COLOUR)
        self.styleByComboBox.addItem("Stratigraphic order", STYLE_ORDER)
        self.styleByComboBox.addItem("Thickness", STYLE_THICKNESS)
        self.styleByComboBox.setToolTip(
            "Unit colour: a categorized style with the colour of each unit.\n"
            "Stratigraphic order: write a 'strat_order' field (0 = first unit in the "
            "column) and use a graduated style.\n"
            "Thickness: write a 'strat_thickness' field and use a graduated style."
        )
        self.strat_ageColorRampComboBox = QComboBox()
        ramp_names = sorted(QgsStyle().defaultStyle().colorRampNames())
        self.strat_ageColorRampComboBox.addItems(ramp_names)
        default_ramp_index = self.strat_ageColorRampComboBox.findText('Viridis')
        if default_ramp_index >= 0:
            self.strat_ageColorRampComboBox.setCurrentIndex(default_ramp_index)
        self.styleByComboBox.currentIndexChanged.connect(self._on_style_by_changed)
        self.applyStyleButton = QPushButton("Apply")
        self.applyStyleButton.setToolTip("Style the geology layer above.")
        self.applyStyleButton.clicked.connect(self.apply_style_to_layer)
        form.addRow("Style by", self.styleByComboBox)
        form.addRow("Colour ramp", self.strat_ageColorRampComboBox)
        form.addRow(self.applyStyleButton)
        self._on_style_by_changed()
        return group

    def _on_style_by_changed(self, _index=None):
        """A colour ramp is only for the graduated styles."""
        self.strat_ageColorRampComboBox.setEnabled(
            self.styleByComboBox.currentData() != STYLE_COLOUR
        )

    def apply_style_to_layer(self):
        """Style the geology layer in the way that the "Style by" combo gives."""
        style = self.styleByComboBox.currentData()
        if style == STYLE_ORDER:
            self.apply_age_to_layer()
        elif style == STYLE_THICKNESS:
            self.apply_thickness_to_layer()
        else:
            self.apply_colours_to_layer()

    def _add_empty_list_text(self):
        """Add a text on the list that shows when the list has no rows."""
        self._emptyListLabel = QLabel(
            "The column is empty.\nUse '+ Unit' to add a unit, or 'Build column' "
            "to add the units from the map.",
            self.unitList.viewport(),
        )
        self._emptyListLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._emptyListLabel.setWordWrap(True)
        self._emptyListLabel.setEnabled(False)
        self._emptyListLabel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        viewport_layout = QVBoxLayout(self.unitList.viewport())
        viewport_layout.addWidget(self._emptyListLabel)

    def _update_list_state(self):
        """Refresh the parts that depend on the rows of the list."""
        try:
            self._emptyListLabel.setVisible(self.unitList.count() == 0)
            self._update_unit_names_summary()
        except RuntimeError:
            # the widget was deleted
            pass

    def _update_unit_names_summary(self):
        """Show how many unit names have no match in the geology layer."""
        names = [
            widget.name
            for widget, _item in self._widget_cache.values()
            if isinstance(widget, StratigraphicUnitWidget) and widget.name
        ]
        if self._known_unit_names is None:
            text = "Select a layer and a unit name field to check the unit names."
        elif not names:
            text = "The column has no units."
        else:
            missing = [name for name in names if name not in self._known_unit_names]
            if missing:
                text = (
                    f"Warning: {len(missing)} of {len(names)} units have no match in the "
                    f"layer: {', '.join(missing)}"
                )
            else:
                text = f"All {len(names)} units match a name in the layer."
        self.unitNamesSummaryLabel.setText(text)

    def clearColumn(self):
        """Clear the stratigraphic column, after the user confirms."""
        if self.unitList.count() > 0:
            reply = QMessageBox.question(
                self,
                "Clear Stratigraphic Column",
                "This removes all units and unconformities from the stratigraphic column. "
                "This cannot be undone.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
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

    def reverseColumn(self):
        """Reverse the order of the stratigraphic column (units and unconformities)."""
        if not self.data_manager or not self.data_manager._stratigraphic_column:
            return
        uuids = [element.uuid for element in self.data_manager._stratigraphic_column.order]
        if len(uuids) < 2:
            return
        self.data_manager.update_stratigraphic_column_order(list(reversed(uuids)))

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

            # `order` is oldest first (the base is index 0). Show the youngest
            # unit at the top of the list, as in a stratigraphic column.
            current_order = list(reversed(self.data_manager._stratigraphic_column.order))
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
                            unit_data = unit.to_dict()
                            if isinstance(widget, UnconformityWidget):
                                unit_data = self._enrich_unconformity_data(unit_data)
                                widget.set_available_faults(self._get_available_fault_names())
                            widget.setData(unit_data)
                return

            # If order/content differs, do a full rebuild
            # but only as a last resort
            self._full_rebuild_display(current_order)
        finally:
            self._updating = False
            self._update_list_state()

    def _full_rebuild_display(self, current_order):
        """Perform a full rebuild of the display (called only when necessary).

        Parameters
        ----------
        current_order : list
            The elements of the stratigraphic column in display order
            (youngest first)
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
                self.add_unconformity(
                    unconformity_data=self._enrich_unconformity_data(unit.to_dict()),
                    create_new=False,
                )

    def _enrich_unconformity_data(self, unconformity_data):
        """Merge in the plugin-side fault-boundary link for an unconformity row.

        `StratigraphicUnconformity.to_dict()` (core) only knows `erode`/
        `onlap`; the fault link is tracked separately in the data manager
        (see `ModellingDataManager.set_fault_boundary`), so it has to be
        folded in here for display.
        """
        fault_name = self.data_manager.get_fault_boundary(unconformity_data.get('uuid'))
        if fault_name:
            unconformity_data = dict(unconformity_data)
            unconformity_data['unconformity_type'] = 'fault'
            unconformity_data['fault_name'] = fault_name
            unconformity_data['flipped'] = self.data_manager.is_fault_boundary_flipped(
                unconformity_data.get('uuid')
            )
        return unconformity_data

    def _get_available_fault_names(self):
        """Fault names offered when marking an unconformity as a domain boundary."""
        if not self.data_manager:
            return []
        return list(self.data_manager._fault_topology.faults)

    def init_stratigraphic_column_from_basal_contacts(self):
        if self.data_manager:
            self.data_manager.init_stratigraphic_column_from_basal_contacts()
            self.update_display()
        else:
            print("Error: Data manager is not initialized.")

    def init_stratigraphic_column_from_layer_field(self):
        if not self.data_manager:
            print("Error: Data manager is not initialized.")
            return
        dialog = InitFromLayerFieldDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        layer = dialog.selected_layer()
        field_name = dialog.selected_field()
        applied = self.data_manager.init_stratigraphic_column_from_layer_field(layer, field_name)
        if applied:
            self.update_display()
        else:
            QMessageBox.warning(
                self,
                "Initialise from Layer Field",
                f"Could not initialise the stratigraphic column. No values were found in "
                f"field '{field_name}'.",
            )

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
        field = self.unitsLayerFieldComboBox.currentField()
        self.data_manager.set_widget_settings(
            'stratigraphic_column_widget',
            {
                'units_layer': layer.name() if layer else None,
                'units_layer_field': field,
            },
        )
        # The geology layer is shared with the map2loop tools
        if not self._syncing_roles:
            self.data_manager.layer_roles.set(layer_roles.GEOLOGY, layer)
            self.data_manager.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, field or None)

    def _sync_units_layer_from_roles(self):
        """Show the geology layer and the unit name field of the shared roles."""
        roles = self.data_manager.layer_roles
        layer = roles.get(layer_roles.GEOLOGY)
        field = roles.get(layer_roles.GEOLOGY_UNIT_FIELD)
        if layer is None:
            return
        self._syncing_roles = True
        try:
            if self.unitsLayerComboBox.currentLayer() != layer:
                self.unitsLayerComboBox.setLayer(layer)
            if field and layer.fields().indexFromName(field) >= 0:
                self.unitsLayerFieldComboBox.setField(field)
        finally:
            self._syncing_roles = False
        self._revalidate_unit_names()

    def _on_layer_role_changed(self, role, value):
        """Follow a change of the geology role that did not come from this widget."""
        if role in (layer_roles.GEOLOGY, layer_roles.GEOLOGY_UNIT_FIELD):
            try:
                self._sync_units_layer_from_roles()
            except RuntimeError:
                # the widget was deleted
                pass

    def _on_units_field_changed(self, _field_name):
        """Persist and re-validate when the unit-name field selection changes."""
        self._persist_units_layer_selection()
        self._revalidate_unit_names()
        self.highlight_selected_unit()

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
        self.highlight_selected_unit()

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
        self._update_unit_names_summary()

    def highlight_selected_unit(self):
        """Select the features of the selected unit in the units layer, so
        that QGIS highlights them on the map.

        Clears the highlight when no unit row is selected (for example an
        unconformity row) or when no units layer/field is set.
        """
        try:
            items = self.unitList.selectedItems()
        except RuntimeError:
            # Widget was deleted
            return
        widget = self.unitList.itemWidget(items[0]) if items else None
        layer = self.unitsLayerComboBox.currentLayer()
        field_name = self.unitsLayerFieldComboBox.currentField()

        self._clear_unit_highlight()
        if (
            not isinstance(widget, StratigraphicUnitWidget)
            or not widget.name
            or layer is None
            or not field_name
            or layer.fields().indexFromName(field_name) < 0
        ):
            return
        expression = f"{QgsExpression.quotedColumnRef(field_name)} = {QgsExpression.quotedValue(widget.name)}"
        layer.selectByExpression(expression)
        self._highlighted_layer = layer

    def _clear_unit_highlight(self):
        """Remove the feature selection made by highlight_selected_unit."""
        layer = self._highlighted_layer
        self._highlighted_layer = None
        if layer is None:
            return
        try:
            layer.removeSelection()
        except RuntimeError:
            # Layer was removed from the project
            pass

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
            push_success(
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
            push_success(
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

    def apply_thickness_to_layer(self):
        """Write each unit's thickness onto the selected units layer and style it by a graduated ramp."""
        if not self.data_manager:
            print("Error: Data manager is not initialized.")
            return
        layer = self.unitsLayerComboBox.currentLayer()
        field_name = self.unitsLayerFieldComboBox.currentField()
        if layer is None or not field_name:
            QMessageBox.warning(
                self,
                "Apply Stratigraphic Thickness to Map Layer",
                "Please select a units layer and unit name field above.",
            )
            return
        ramp_name = self.strat_ageColorRampComboBox.currentText()
        applied = self.data_manager.apply_stratigraphic_thickness_to_layer(
            layer, field_name, ramp_name=ramp_name
        )
        if applied:
            push_success(
                "Apply Stratigraphic Thickness to Map Layer",
                f"Applied stratigraphic thickness and graduated styling to layer "
                f"'{layer.name()}'.",
            )
        else:
            QMessageBox.warning(
                self,
                "Apply Stratigraphic Thickness to Map Layer",
                "Could not apply stratigraphic thickness. The stratigraphic column may "
                "have no units, or no features matched a stratigraphic unit.",
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
        unit_widget.nameChanged.connect(lambda: self._on_unit_name_changed(unit_widget))

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
        self._add_list_item(item, at_top=create_new)
        self.unitList.setItemWidget(item, unit_widget)
        unit_widget.focused.connect(lambda: self.unitList.setCurrentItem(item))
        unit_widget.setData(unit_data)  # Set data for the unit widget
        unit_widget.set_known_unit_names(self._known_unit_names)

        # Cache the widget for efficient updates
        self._widget_cache[unit_data['uuid']] = (unit_widget, item)
        self._update_list_state()

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
                widget.set_available_faults(self._get_available_fault_names())
                widget.setData(unconformity_data)
            return

        unconformity_widget = UnconformityWidget(uuid=unconformity.uuid)
        unconformity_widget.deleteRequested.connect(self.delete_unit)
        unconformity_widget.dataChanged.connect(lambda: self.update_element(unconformity_widget))
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
        # An unconformity row has another background than a unit row
        item.setBackground(QBrush(self.palette().alternateBase()))
        item.setSizeHint(unconformity_widget.sizeHint())
        self._add_list_item(item, at_top=create_new)
        self.unitList.setItemWidget(item, unconformity_widget)
        unconformity_widget.set_available_faults(self._get_available_fault_names())
        unconformity_widget.setData(unconformity_data)

        # Cache the widget for efficient updates
        self._widget_cache[unconformity.uuid] = (unconformity_widget, item)
        self._update_list_state()

    def _on_unit_name_changed(self, unit_widget):
        """Update the summary, and the map highlight when the selected unit is renamed."""
        self._update_unit_names_summary()
        try:
            items = self.unitList.selectedItems()
        except RuntimeError:
            return
        if items and self.unitList.itemWidget(items[0]) is unit_widget:
            self.highlight_selected_unit()

    def _add_list_item(self, item, *, at_top):
        """Add a row to the list. A new element goes on top of the column
        (the end of `order`), so it is shown in the first row."""
        if at_top:
            self.unitList.insertItem(0, item)
        else:
            self.unitList.addItem(item)

    def _ordered_uuids_from_rows(self):
        """Return the uuids of the rows in `order` sequence (oldest first).
        The rows are shown youngest first, so they are reversed."""
        uuids = []
        for i in range(self.unitList.count()):
            widget = self.unitList.itemWidget(self.unitList.item(i))
            if widget:
                uuids.append(widget.uuid)
            else:
                print(f"Warning: Item at index {i} has no widget associated with it.")
        return list(reversed(uuids))

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
        self._update_list_state()

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

        row_uuids = [
            self.unitList.itemWidget(self.unitList.item(i)).uuid
            for i in range(self.unitList.count())
        ]
        try:
            current_row = row_uuids.index(widget.uuid)
        except ValueError:
            return
        if current_row == target_row:
            return
        row_uuids.pop(current_row)
        row_uuids.insert(target_row, widget.uuid)
        # rows are youngest first, `order` is oldest first
        self.data_manager.update_stratigraphic_column_order(list(reversed(row_uuids)))

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
            self.data_manager.update_stratigraphic_column_order(self._ordered_uuids_from_rows())

    def update_element(self, unit_widget):
        """Update the data manager with the changes made in the unit widget.

        After updating the element, triggers the callback to notify all listeners
        (including other widgets) that the stratigraphic column has changed.
        """
        if self.data_manager:
            unit_data = unit_widget.getData()
            if isinstance(unit_widget, UnconformityWidget):
                fault_name = unit_data.pop('fault_name', None)
                flipped = unit_data.pop('flipped', False)
                is_fault_boundary = unit_data.get('unconformity_type') == 'fault'
                if is_fault_boundary:
                    # The core stratigraphic column only knows erode/onlap --
                    # the fault link lives in the data manager's side table
                    # (see set_fault_boundary), so store it as a plain
                    # erosional boundary here.
                    unit_data['unconformity_type'] = 'erode'
                if is_fault_boundary and fault_name:
                    previous_fault_name = self.data_manager.get_fault_boundary(unit_widget.uuid)
                    self.data_manager.set_fault_boundary(
                        unit_widget.uuid, fault_name, flipped=flipped
                    )
                    # Only warn when the fault changes, not on a polarity flip.
                    if fault_name != previous_fault_name and (
                        not self.data_manager.fault_spans_model_domain(fault_name)
                    ):
                        QMessageBox.information(
                            self,
                            "Fault Domain Boundary",
                            f"Fault '{fault_name}' does not reach every edge of the model "
                            "bounding box.\n\nA fault used as a domain boundary crops the "
                            "whole model, so its digitised trace will automatically be "
                            "extended out to the domain edges along its overall trend when "
                            "the model is built. For best results the trace should still "
                            "roughly follow the fault's real direction across the gap.",
                        )
                else:
                    self.data_manager.clear_fault_boundary(unit_widget.uuid)
            if not isinstance(unit_widget, UnconformityWidget):
                # a thickness that the user typed must not be replaced by a
                # calculated thickness
                self.data_manager.note_thickness_edit(unit_data)
            self.data_manager._stratigraphic_column.update_element(unit_data)
            # Trigger callback to notify all listeners of the change
            if self.data_manager.stratigraphic_column_callback:
                self.data_manager.stratigraphic_column_callback()
