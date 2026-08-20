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
        self.comboBoxUnconformityType.currentIndexChanged.connect(self._on_type_changed)
        self.comboBoxFaultName.currentIndexChanged.connect(self._on_fault_name_changed)
        # The row's combo box/buttons cover the whole widget, so a QListWidget's
        # built-in drag-and-drop can never see a mouse press to start a
        # reorder. Route presses on the dedicated grip label through here instead.
        self._dragging_handle = False
        self.dragHandle.setCursor(Qt.SizeVerCursor)
        self.dragHandle.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.dragHandle:
            event_type = event.type()
            if event_type == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging_handle = True
                self.dragHandlePressed.emit()
                return True
            elif event_type == QEvent.MouseMove and self._dragging_handle:
                self.dragHandleMoved.emit(event_global_pos(event))
                return True
            elif event_type == QEvent.MouseButtonRelease and self._dragging_handle:
                self._dragging_handle = False
                self.dragHandleReleased.emit()
                return True
        return super().eventFilter(obj, event)

    def request_delete(self):

        self.deleteRequested.emit(self)

    def _on_type_changed(self, _index):
        self.unconformity_type = self.comboBoxUnconformityType.currentText()
        self.comboBoxFaultName.setVisible(self.unconformity_type == 'fault')
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

    def set_available_faults(self, fault_names):
        """Populate the fault-name picker, keeping the current selection if
        it is still available (e.g. after the fault trace layer changes).
        """
        fault_names = list(fault_names or [])
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
            'fault'), and a 'fault_name' key when the type is 'fault'. If
            None, defaults are used.
        """
        self.unconformity_type = (data or {}).get("unconformity_type", "erode")
        self.fault_name = (
            (data or {}).get("fault_name") if self.unconformity_type == 'fault' else None
        )

        self.comboBoxUnconformityType.blockSignals(True)
        self.comboBoxFaultName.blockSignals(True)
        try:
            index = self.comboBoxUnconformityType.findText(self.unconformity_type)
            if index >= 0:
                self.comboBoxUnconformityType.setCurrentIndex(index)
            self.comboBoxFaultName.setVisible(self.unconformity_type == 'fault')
            if self.fault_name:
                self.comboBoxFaultName.setCurrentText(self.fault_name)
        finally:
            self.comboBoxUnconformityType.blockSignals(False)
            self.comboBoxFaultName.blockSignals(False)

    def getData(self):
        """Return this row's data for the data manager: uuid, unconformity_type
        and (when the boundary is fault-linked) fault_name.
        """
        return {
            'uuid': self.uuid,
            'unconformity_type': self.unconformity_type,
            'fault_name': self.fault_name,
        }
