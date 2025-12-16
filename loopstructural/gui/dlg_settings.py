#! python3

"""Plugin settings form integrated into QGIS 'Options' menu."""

# standard
import platform
from functools import partial
from pathlib import Path
from urllib.parse import quote

# PyQGIS
from qgis.core import Qgis, QgsApplication
from qgis.gui import QgsOptionsPageWidget, QgsOptionsWidgetFactory
from qgis.PyQt import uic
from qgis.PyQt.Qt import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon

# project
from loopstructural.__about__ import (
    __icon_path__,
    __title__,
    __uri_homepage__,
    __uri_tracker__,
    __version__,
)
from loopstructural.toolbelt import PlgLogger, PlgOptionsManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure

# ############################################################################
# ########## Globals ###############
# ##################################

FORM_CLASS, _ = uic.loadUiType(Path(__file__).parent / "{}.ui".format(Path(__file__).stem))


# ############################################################################
# ########## Classes ###############
# ##################################


class ConfigOptionsPage(FORM_CLASS, QgsOptionsPageWidget):
    """Settings form embedded into QGIS 'options' menu."""

    def __init__(self, parent):
        super().__init__(parent)
        self.log = PlgLogger().log
        self.plg_settings = PlgOptionsManager()

        # load UI and set objectName
        self.setupUi(self)
        self.setObjectName("mOptionsPage{}".format(__title__))

        _report_context_message = quote(
            "> Reported from plugin settings\n\n"
            f"- operating system: {platform.system()} "
            f"{platform.release()}_{platform.version()}\n"
            f"- QGIS: {Qgis.QGIS_VERSION}"
            f"- plugin version: {__version__}\n"
        )

        # header
        self.lbl_title.setText(f"{__title__} - Version {__version__}")

        # customization
        self.btn_help.setIcon(QIcon(QgsApplication.iconPath("mActionHelpContents.svg")))
        self.btn_help.pressed.connect(partial(QDesktopServices.openUrl, QUrl(__uri_homepage__)))

        self.btn_report.setIcon(
            QIcon(QgsApplication.iconPath("console/iconSyntaxErrorConsole.svg"))
        )

        self.btn_report.pressed.connect(
            partial(QDesktopServices.openUrl, QUrl(f"{__uri_tracker__}new/choose"))
        )

        self.btn_reset.setIcon(QIcon(QgsApplication.iconPath("mActionUndo.svg")))
        self.btn_reset.pressed.connect(self.reset_settings)

        if hasattr(self, "btn_browse_debug_directory"):
            self.btn_browse_debug_directory.pressed.connect(self._browse_debug_directory)
        if hasattr(self, "btn_open_debug_directory"):
            self.btn_open_debug_directory.pressed.connect(self._open_debug_directory)

        # load previously saved settings
        self.load_settings()

    def apply(self):
        """Apply settings from the form and persist them to QgsSettings."""
        settings = self.plg_settings.get_plg_settings()

        # misc
        settings.debug_mode = self.opt_debug.isChecked()
        settings.separate_dock_widgets = self.opt_separate_dock_widgets.isChecked()
        settings.interpolator_nelements = self.n_elements_spin_box.value()
        settings.interpolator_npw = self.npw_spin_box.value()
        settings.interpolator_cpw = self.cpw_spin_box.value()
        settings.interpolator_regularisation = self.regularisation_spin_box.value()
        settings.version = __version__
        debug_dir_text = (self.le_debug_directory.text() if hasattr(self, "le_debug_directory") else "") or ""
        self.plg_settings.set_debug_directory(debug_dir_text)
        settings.debug_directory = debug_dir_text

        # dump new settings into QgsSettings
        self.plg_settings.save_from_object(settings)

        if __debug__:
            self.log(
                message="DEBUG - Settings successfully saved.",
                log_level=4,
            )

    def load_settings(self):
        """Load options from QgsSettings into the UI form."""
        settings = self.plg_settings.get_plg_settings()

        # global
        self.opt_debug.setChecked(settings.debug_mode)
        self.opt_separate_dock_widgets.setChecked(settings.separate_dock_widgets)
        self.lbl_version_saved_value.setText(settings.version)
        # self.interpolator_type_combo.setCurrentText(settings.interpolator_type)
        self.n_elements_spin_box.setValue(settings.interpolator_nelements)
        self.regularisation_spin_box.setValue(settings.interpolator_regularisation)
        self.cpw_spin_box.setValue(settings.interpolator_cpw)
        self.npw_spin_box.setValue(settings.interpolator_npw)
        if hasattr(self, "le_debug_directory"):
            self.le_debug_directory.setText(settings.debug_directory or "")

    def reset_settings(self):
        """Reset settings in the UI and persisted settings to plugin defaults."""
        default_settings = PlgSettingsStructure()

        # dump default settings into QgsSettings
        self.plg_settings.save_from_object(default_settings)

        # update the form
        self.load_settings()

    def _browse_debug_directory(self):
        """Open a directory selector for debug directory."""
        from qgis.PyQt.QtWidgets import QFileDialog

        start_dir = (self.le_debug_directory.text() if hasattr(self, "le_debug_directory") else "") or ""
        chosen = QFileDialog.getExistingDirectory(self, "Select Debug Files Directory", start_dir)
        if chosen and hasattr(self, "le_debug_directory"):
            self.le_debug_directory.setText(chosen)

    def _open_debug_directory(self):
        """Open configured debug directory in the system file manager."""
        target = self.plg_settings.get_debug_directory() or ""
        if target:
            target_path = Path(target)
            if target_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            else:
                self.log(
                    message=f"[map2loop] Debug directory does not exist: {target}",
                    log_level=1,
                )
        else:
            self.log(message="[map2loop] No debug directory configured.", log_level=1)


class PlgOptionsFactory(QgsOptionsWidgetFactory):
    """Factory for options widget."""

    def __init__(self, *args, **kwargs):
        """Initialize the options factory.

        Parameters
        ----------
        *args, **kwargs
            Forwarded to base factory initializer.
        """
        super().__init__()

    def icon(self):
        """Return the icon used for the options page.

        Returns
        -------
        QIcon
            Icon for the options page.
        """
        return QIcon(str(__icon_path__))

    def createWidget(self, parent) -> ConfigOptionsPage:
        """Create settings widget.

        Parameters
        ----------
        parent : QObject
            Qt parent where to include the options page.

        Returns
        -------
        ConfigOptionsPage
            Instantiated options page.
        """
        return ConfigOptionsPage(parent)

    def title(self) -> str:
        """Plugin title used to name options tab.

        Returns
        -------
        str
            Plugin title string.
        """
        return __title__

    def helpId(self) -> str:
        """Plugin help URL.

        Returns
        -------
        str
            URL of the plugin homepage.
        """
        return __uri_homepage__
