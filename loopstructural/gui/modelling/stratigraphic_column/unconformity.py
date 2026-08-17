import os
from typing import Optional

from qgis.PyQt import uic
from qgis.PyQt.QtCore import QEvent, QPoint, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget

from loopstructural.gui.compatibility import event_global_pos


class UnconformityWidget(QWidget):
    deleteRequested = pyqtSignal(QWidget)  # Signal to request deletion
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
        # self.comboBoxUnconformityType.currentIndexChanged.connect(
        #     lambda: setattr(self, 'unconformity_type', self.comboBoxUnconformityType.currentText())
        # )
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

    def setData(self, data: Optional[dict] = None):
        """Set the data for the unconformity widget.

        Parameters
        ----------
        data : dict or None
            Dictionary containing 'unconformity_type' key. If None, defaults are used.
        """
        if data:
            self.unconformity_type = data.get("unconformity_type", "")
            # self.unconformityTypeComboBox.setCurrentIndex(
            #     self.unconformityTypeComboBox.findText(self.unconformity_type)
            # )
        else:
            self.unconformity_type = 'erode'
            # self.unconformityTypeComboBox.setCurrentIndex(
            #     self.unconformityTypeComboBox.findText(self.unconformity_type)
            # )
