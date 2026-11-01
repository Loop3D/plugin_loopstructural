"""The header of the modelling dock: Save, Open, Reset and Settings."""

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QToolButton,
    QWidget,
)
from qgis.utils import iface

from loopstructural.__about__ import __title__
from loopstructural.gui.messages import push_success

STATE_FILE_SUFFIX = '.loopstate.json'
STATE_FILE_FILTER = f"LoopStructural State (*{STATE_FILE_SUFFIX})"


class DockHeader(QWidget):
    """The actions that apply to all of the plugin, not to one step."""

    def __init__(self, parent=None, data_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("<b>LoopStructural</b>", self))
        layout.addStretch(1)

        self.saveButton = self._add_button(
            layout,
            "mActionFileSave.svg",
            "Save",
            "Save the loaded data and the geological model to a file.",
            self.on_save_state_clicked,
        )
        self.openButton = self._add_button(
            layout,
            "mActionFileOpen.svg",
            "Open",
            "Open a saved state. It replaces all loaded data and the geological model.",
            self.on_load_state_clicked,
        )
        self.resetButton = self._add_button(
            layout,
            "mActionUndo.svg",
            "Reset",
            "Clear all loaded data, the stratigraphic column, the fault topology and "
            "the geological model.",
            self.on_reset_state_clicked,
        )
        self.settingsButton = self._add_button(
            layout,
            "console/iconSettingsConsole.svg",
            "Settings",
            "Open the settings of the plugin.",
            self.on_settings_clicked,
        )

    def _add_button(self, layout, icon_name, text, tooltip, slot):
        button = QToolButton(self)
        button.setIcon(QgsApplication.getThemeIcon(icon_name))
        button.setText(text)
        button.setToolTip(tooltip)
        button.setAutoRaise(True)
        button.clicked.connect(lambda _checked=False: slot())
        layout.addWidget(button)
        return button

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
            push_success("Save Application State", f"Application state saved to: {filepath}")

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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
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
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.data_manager.reset()

    def on_settings_clicked(self):
        """Open the settings page of the plugin."""
        if iface is not None:
            iface.showOptionsDialog(currentPage=f"mOptionsPage{__title__}")
