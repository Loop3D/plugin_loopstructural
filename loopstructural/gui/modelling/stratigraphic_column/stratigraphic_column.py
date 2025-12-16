from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumnElementType
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget

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
        item = QListWidgetItem()
        item.setSizeHint(unit_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unit_widget)
        unit_widget.setData(unit_data)  # Set data for the unit widget

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
