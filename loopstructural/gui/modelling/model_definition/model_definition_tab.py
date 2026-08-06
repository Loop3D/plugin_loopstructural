from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from loopstructural.gui.modelling.base_tab import BaseTab

from .bounding_box import BoundingBoxWidget
from .dem import DEMWidget
from .fault_layers import FaultLayersWidget
from .stratigraphic_layers import StratigraphicLayersWidget

STATE_FILE_SUFFIX = '.loopstate.json'
STATE_FILE_FILTER = f"LoopStructural State (*{STATE_FILE_SUFFIX})"


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

        actions_widget = QWidget(self)
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        self.saveStateButton = QPushButton("Save State")
        self.saveStateButton.setIcon(QgsApplication.getThemeIcon("mActionFileSave.svg"))
        self.saveStateButton.setToolTip(
            "Save the currently loaded data and geological model to a file."
        )
        self.saveStateButton.clicked.connect(self.on_save_state_clicked)

        self.loadStateButton = QPushButton("Load State")
        self.loadStateButton.setIcon(QgsApplication.getThemeIcon("mActionFileOpen.svg"))
        self.loadStateButton.setToolTip(
            "Load a previously saved application state, replacing all currently "
            "loaded data and the geological model."
        )
        self.loadStateButton.clicked.connect(self.on_load_state_clicked)

        self.resetStateButton = QPushButton("Reset Application State")
        self.resetStateButton.setIcon(QgsApplication.getThemeIcon("mActionUndo.svg"))
        self.resetStateButton.setToolTip(
            "Clear all loaded data, the stratigraphic column, fault topology and "
            "the geological model, restoring the plugin to its initial state."
        )
        self.resetStateButton.clicked.connect(self.on_reset_state_clicked)

        actions_layout.addWidget(self.saveStateButton)
        actions_layout.addWidget(self.loadStateButton)
        actions_layout.addWidget(self.resetStateButton)
        self.add_widget(actions_widget, group_box=False)

        self.add_widget(self.bounding_box, 'Bounding Box')  # , "Bounding Box")
        self.add_widget(self.dem, 'DEM')
        self.add_widget(self.fault_layers, 'Fault Layers')  # , "Fault Layers")
        self.add_widget(
            self.stratigraphy_layers, 'Stratigraphic Layers'
        )  # , "Stratigraphic Layers")

    def on_save_state_clicked(self):
        """Prompt for a destination file and save the current app state to it."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Application State", "", STATE_FILE_FILTER
        )
        if not filepath:
            return
        if not filepath.endswith(STATE_FILE_SUFFIX):
            filepath += STATE_FILE_SUFFIX
        try:
            self.data_manager.save_state(filepath)
        except Exception as err:
            QMessageBox.critical(
                self, "Save Application State", f"Failed to save application state:\n{err}"
            )
        else:
            QMessageBox.information(
                self, "Save Application State", f"Application state saved to:\n{filepath}"
            )

    def on_load_state_clicked(self):
        """Prompt for a state file and, after confirmation, load it."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Application State", "", STATE_FILE_FILTER
        )
        if not filepath:
            return
        reply = QMessageBox.question(
            self,
            "Load Application State",
            "Loading a saved state will replace all currently loaded data and "
            "the geological model. This cannot be undone.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self.data_manager.load_state(filepath)
        except Exception as err:
            QMessageBox.critical(
                self, "Load Application State", f"Failed to load application state:\n{err}"
            )

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
