from PyQt5.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.stratigraphic_column.unconformity import UnconformityWidget
from LoopStructural.modelling.core.stratigraphic_column import StratigraphicColumnElementType

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
    """

    def __init__(self, parent=None, data_manager=None):
        super().__init__()
        layout = QVBoxLayout(self)
        if data_manager is None:
            raise ValueError("Data manager must be provided.")
        self.data_manager = data_manager
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
        self.unitList.clear()
        if self.data_manager:
            self.data_manager._stratigraphic_column.clear()
        else:
            print("Error: Data manager is not initialized.")

    def update_display(self):
        """Update the widget display based on the data manager's stratigraphic column."""
        self.unitList.clear()
        if self.data_manager and self.data_manager._stratigraphic_column:
            for unit in self.data_manager._stratigraphic_column.order:
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
        unit_data.pop('type', None)  # Remove type if present
        unit_data.pop('id', None)
        for k in list(unit_data.keys()):
            if unit_data[k] is None:
                unit_data.pop(k)
        print(f"Adding unit with data: {unit_data}")
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
        # Update data manager

    def add_unconformity(self, *, unconformity_data=None, create_new=True):
        if unconformity_data is None:
            unconformity_data = {'type': 'unconformity', 'unconformity_type': 'erode'}
        if create_new:
            unconformity = self.data_manager.add_to_stratigraphic_column(unconformity_data)
        else:
            unconformity = self.data_manager._stratigraphic_column.get_element_by_uuid(
                unconformity_data['uuid']
            )

        unconformity_widget = UnconformityWidget(uuid=unconformity.uuid)
        unconformity_widget.deleteRequested.connect(self.delete_unit)
        item = QListWidgetItem()
        item.setSizeHint(unconformity_widget.sizeHint())
        self.unitList.addItem(item)
        self.unitList.setItemWidget(item, unconformity_widget)

        # Update data manager

    def delete_unit(self, unit_widget):
        for i in range(self.unitList.count()):
            item = self.unitList.item(i)
            if self.unitList.itemWidget(item) == unit_widget:
                self.unitList.takeItem(i)
                break

        # Update data manager
        if self.data_manager:
            self.data_manager.remove_from_stratigraphic_column(unit_widget.uuid)

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
        """Update the data manager with the changes made in the unit widget."""
        if self.data_manager:
            unit_data = unit_widget.getData()
            self.data_manager._stratigraphic_column.update_element(unit_data)
