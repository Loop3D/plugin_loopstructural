from qgis.core import QgsMapLayerProxyModel
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QVBoxLayout

from loopstructural.gui.compatibility import configure_layer_combo


class InitFromLayerFieldDialog(QDialog):
    """Dialog for picking a polygon layer and a field whose unique values
    seed the stratigraphic column."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Initialise Stratigraphic Column from Layer Field")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.layerComboBox = QgsMapLayerComboBox()
        configure_layer_combo(
            self.layerComboBox, QgsMapLayerProxyModel.PolygonLayer, allow_empty=True
        )
        self.layerComboBox.setCurrentIndex(-1)
        form_layout.addRow("Layer:", self.layerComboBox)

        self.fieldComboBox = QgsFieldComboBox()
        self.layerComboBox.layerChanged.connect(self.fieldComboBox.setLayer)
        form_layout.addRow("Field:", self.fieldComboBox)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self):
        if self.layerComboBox.currentLayer() is None or not self.fieldComboBox.currentField():
            QMessageBox.warning(
                self,
                "Initialise Stratigraphic Column from Layer Field",
                "Please select a layer and a field.",
            )
            return
        self.accept()

    def selected_layer(self):
        return self.layerComboBox.currentLayer()

    def selected_field(self):
        return self.fieldComboBox.currentField()
