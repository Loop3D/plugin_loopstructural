from qgis.PyQt.QtWidgets import QMessageBox, QPushButton, QSizePolicy

from loopstructural.gui.modelling.base_tab import BaseTab

from .bounding_box import BoundingBoxWidget
from .dem import DEMWidget
from .fault_layers import FaultLayersWidget
from .stratigraphic_layers import StratigraphicLayersWidget


class ModelDefinitionTab(BaseTab):
    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent, data_manager, scrollable=True)
        # Add widgets to the QToolBox
        self.bounding_box = BoundingBoxWidget(self, data_manager)
        self.dem = DEMWidget(self, data_manager)
        self.fault_layers = FaultLayersWidget(self, data_manager)
        self.stratigraphy_layers = StratigraphicLayersWidget(self, data_manager)

        # Set uniform size policy for all widgets
        for widget in [self.bounding_box, self.fault_layers, self.dem, self.stratigraphy_layers]:
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.resetStateButton = QPushButton("Reset Application State")
        self.resetStateButton.setToolTip(
            "Clear all loaded data, the stratigraphic column, fault topology and "
            "the geological model, restoring the plugin to its initial state."
        )
        self.resetStateButton.clicked.connect(self.on_reset_state_clicked)
        self.add_widget(self.resetStateButton, group_box=False)

        self.add_widget(self.bounding_box, 'Bounding Box')  # , "Bounding Box")
        self.add_widget(self.dem, 'DEM')
        self.add_widget(self.fault_layers, 'Fault Layers')  # , "Fault Layers")
        self.add_widget(
            self.stratigraphy_layers, 'Stratigraphic Layers'
        )  # , "Stratigraphic Layers")

    def on_reset_state_clicked(self):
        """Prompt for confirmation, then reset the data and model managers."""
        reply = QMessageBox.question(
            self,
            "Reset Application State",
            "This will clear all loaded data, the stratigraphic column, fault "
            "topology and the geological model. This cannot be undone.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.data_manager.reset()
