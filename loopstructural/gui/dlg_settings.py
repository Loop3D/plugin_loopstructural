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

        # load previously saved settings
        self.load_settings()

    def apply(self):
        """Called to permanently apply the settings shown in the options page (e.g. \
        save them to QgsSettings objects). This is usually called when the options \
        dialog is accepted.
        """
        settings = self.plg_settings.get_plg_settings()

        # misc
        settings.debug_mode = self.opt_debug.isChecked()
        settings.interpolator_nelements = self.n_elements_spin_box.value()
        settings.interpolator_npw = self.npw_spin_box.value()
        settings.interpolator_cpw = self.cpw_spin_box.value()
        settings.interpolator_regularisation = self.regularisation_spin_box.value()
        settings.version = __version__

        # dump new settings into QgsSettings
        self.plg_settings.save_from_object(settings)

        if __debug__:
            self.log(
                message="DEBUG - Settings successfully saved.",
                log_level=4,
            )

    def load_settings(self):
        """Load options from QgsSettings into UI form."""
        settings = self.plg_settings.get_plg_settings()

        # global
        self.opt_debug.setChecked(settings.debug_mode)
        self.lbl_version_saved_value.setText(settings.version)
        # self.interpolator_type_combo.setCurrentText(settings.interpolator_type)
        self.n_elements_spin_box.setValue(settings.interpolator_nelements)
        self.regularisation_spin_box.setValue(settings.interpolator_regularisation)
        self.cpw_spin_box.setValue(settings.interpolator_cpw)
        self.npw_spin_box.setValue(settings.interpolator_npw)

    def reset_settings(self):
        """Reset settings to default values (set in preferences.py module)."""
        default_settings = PlgSettingsStructure()

        # dump default settings into QgsSettings
        self.plg_settings.save_from_object(default_settings)

        # update the form
        self.load_settings()


class PlgOptionsFactory(QgsOptionsWidgetFactory):
    """Factory for options widget."""

    def __init__(self):
        """Constructor."""
        super().__init__()

    def icon(self) -> QIcon:
        """Returns plugin icon, used to as tab icon in QGIS options tab widget.

        :return: _description_
        :rtype: QIcon
        """
        return QIcon(str(__icon_path__))

    def createWidget(self, parent) -> ConfigOptionsPage:
        """Create settings widget.

        :param parent: Qt parent where to include the options page.
        :type parent: QObject

        :return: options page for tab widget
        :rtype: ConfigOptionsPage
        """
        return ConfigOptionsPage(parent)

    def title(self) -> str:
        """Returns plugin title, used to name the tab in QGIS options tab widget.

        :return: plugin title from about module
        :rtype: str
        """
        return __title__

    def helpId(self) -> str:
        """Returns plugin help URL.

        :return: plugin homepage url from about module
        :rtype: str
        """
        return __uri_homepage__
