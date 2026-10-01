import os
from typing import Optional

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QEvent, QPoint, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget

from loopstructural.gui.compatibility import event_global_pos


class UnconformityWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion
    dataChanged = pyqtSignal()  # Type or fault-name changed
    dragHandlePressed = pyqtSignal()  # Drag handle mouse-down
    dragHandleMoved = pyqtSignal(QPoint)  # Drag handle mouse-move (global pos)
    dragHandleReleased = pyqtSignal()  # Drag handle mouse-up

    def __init__(
        self,
        uuid,
        parent=None,
    ):
        super().__init__(parent)
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'unconformity.ui'), self)
        # Add delete button
        self.buttonDelete.clicked.connect(self.request_delete)
        self.uuid = uuid
        self.unconformity_type = 'erode'
        self.fault_name = None
        self.flipped = False
        self.comboBoxUnconformityType.currentIndexChanged.connect(self._on_type_changed)
        self.comboBoxFaultName.currentIndexChanged.connect(self._on_fault_name_changed)
        self.buttonFlipPolarity.toggled.connect(self._on_flip_toggled)
        self._update_flip_button()
        # The row's combo box/buttons cover the whole widget, so a QListWidget's
        # built-in drag-and-drop can never see a mouse press to start a
        # reorder. Route presses on the dedicated grip label through here instead.
        self._dragging_handle = False
        self.dragHandle.setCursor(Qt.CursorShape.SizeVerCursor)
        self.dragHandle.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.dragHandle:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._dragging_handle = True
                self.dragHandlePressed.emit()
                return True
            elif event_type == QEvent.Type.MouseMove and self._dragging_handle:
                self.dragHandleMoved.emit(event_global_pos(event))
                return True
            elif event_type == QEvent.Type.MouseButtonRelease and self._dragging_handle:
                self._dragging_handle = False
                self.dragHandleReleased.emit()
                return True
        return super().eventFilter(obj, event)

    def request_delete(self):

        self.deleteRequested.emit(self)

    def _on_type_changed(self, _index):
        self.unconformity_type = self.comboBoxUnconformityType.currentText()
        self._update_fault_controls_visibility()
        if self.unconformity_type == 'fault':
            self.fault_name = self.comboBoxFaultName.currentText() or None
        else:
            self.fault_name = None
        self.dataChanged.emit()

    def _on_fault_name_changed(self, _index):
        if self.unconformity_type != 'fault':
            return
        self.fault_name = self.comboBoxFaultName.currentText() or None
        self.dataChanged.emit()

    def _on_flip_toggled(self, checked):
        self.flipped = bool(checked)
        self._update_flip_button()
        if self.unconformity_type != 'fault':
            return
        self.dataChanged.emit()

    def _update_flip_button(self):
        """Show on the button if the polarity of the fault boundary is inverted."""
        if self.flipped:
            self.buttonFlipPolarity.setText("⇅ Inverted")
            self.buttonFlipPolarity.setStyleSheet(
                "QToolButton { background-color: #e67e22; color: white; font-weight: bold; }"
            )
        else:
            self.buttonFlipPolarity.setText("⇅ Normal")
            self.buttonFlipPolarity.setStyleSheet("")

    def _update_fault_controls_visibility(self):
        is_fault = self.unconformity_type == 'fault'
        self.comboBoxFaultName.setVisible(is_fault)
        self.buttonFlipPolarity.setVisible(is_fault)

    def set_available_faults(self, fault_names):
        """Populate the fault-name picker, keeping the current selection if
        it is still available (e.g. after the fault trace layer changes).
        """
        fault_names = list(fault_names or [])
        # A fault boundary needs a fault to link to. Without one the row
        # would fall back to 'erode' when the data manager is updated, so
        # do not offer the 'fault' type until a fault exists.
        fault_index = self.comboBoxUnconformityType.findText('fault')
        if fault_index >= 0:
            fault_item = self.comboBoxUnconformityType.model().item(fault_index)
            fault_item.setEnabled(bool(fault_names))
            fault_item.setToolTip(
                ""
                if fault_names
                else "Add a fault trace layer with at least one fault to use a fault boundary"
            )
        if [
            self.comboBoxFaultName.itemText(i) for i in range(self.comboBoxFaultName.count())
        ] == fault_names:
            return
        self.comboBoxFaultName.blockSignals(True)
        try:
            self.comboBoxFaultName.clear()
            self.comboBoxFaultName.addItems(fault_names)
            if self.fault_name and self.fault_name in fault_names:
                self.comboBoxFaultName.setCurrentText(self.fault_name)
        finally:
            self.comboBoxFaultName.blockSignals(False)

    def setData(self, data: Optional[dict] = None):
        """Set the data for the unconformity widget.

        Parameters
        ----------
        data : dict or None
            Dictionary with an 'unconformity_type' key ('erode', 'onlap' or
            'fault'), and 'fault_name' and 'flipped' keys when the type is
            'fault'. If None, defaults are used.
        """
        self.unconformity_type = (data or {}).get("unconformity_type", "erode")
        is_fault = self.unconformity_type == 'fault'
        self.fault_name = (data or {}).get("fault_name") if is_fault else None
        self.flipped = bool((data or {}).get("flipped", False)) if is_fault else False

        self.comboBoxUnconformityType.blockSignals(True)
        self.comboBoxFaultName.blockSignals(True)
        self.buttonFlipPolarity.blockSignals(True)
        try:
            index = self.comboBoxUnconformityType.findText(self.unconformity_type)
            if index >= 0:
                self.comboBoxUnconformityType.setCurrentIndex(index)
            self._update_fault_controls_visibility()
            if self.fault_name:
                self.comboBoxFaultName.setCurrentText(self.fault_name)
            self.buttonFlipPolarity.setChecked(self.flipped)
            self._update_flip_button()
        finally:
            self.comboBoxUnconformityType.blockSignals(False)
            self.comboBoxFaultName.blockSignals(False)
            self.buttonFlipPolarity.blockSignals(False)

    def getData(self):
        """Return this row's data for the data manager: uuid, unconformity_type
        and (when the boundary is fault-linked) fault_name and flipped.
        """
        return {
            'uuid': self.uuid,
            'unconformity_type': self.unconformity_type,
            'fault_name': self.fault_name,
            'flipped': self.flipped,
        }
