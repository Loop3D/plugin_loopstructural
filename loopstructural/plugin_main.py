#! python3

"""Main plugin module."""

# standard
import importlib.util
import os
from functools import partial
from pathlib import Path

# PyQGIS
from qgis.core import QgsApplication, QgsProject, QgsSettings
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QLocale, Qt, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QDockWidget

# project
from loopstructural.__about__ import (
    DIR_PLUGIN_ROOT,
    __icon_path__,
    __title__,
    __uri_homepage__,
)

if importlib.util.find_spec("pyvistaqt") is None:
    raise ImportError(
        "pyvistaqt is not installed. Please install it using the requirements.txt file in the plugin directory."
    )
if importlib.util.find_spec("LoopStructural") is None:
    raise ImportError(
        "LoopStructural is not installed. Please install it using the requirements.txt file in the plugin directory."
    )
from loopstructural.gui.dlg_settings import PlgOptionsFactory
from loopstructural.gui.loop_widget import LoopWidget
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt import PlgLogger

# ############################################################################
# ########## Classes ###############
# ##################################


class LoopstructuralPlugin:
    def __init__(self, iface: QgisInterface):
        """Constructor.

        Parameters
        ----------
        iface : QgisInterface
            An interface instance provided by QGIS which allows the plugin to
            manipulate the QGIS application at run time.
        """
        self.iface = iface
        self.log = PlgLogger().log

        # translation
        # initialize the locale
        self.locale: str = QgsSettings().value("locale/userLocale", QLocale().name())[0:2]
        locale_path: Path = (
            DIR_PLUGIN_ROOT / "resources" / "i18n" / f"{__title__.lower()}_{self.locale}.qm"
        )
        self.log(message=f"Translation: {self.locale}, {locale_path}", log_level=4)
        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path.resolve()))
            QCoreApplication.installTranslator(self.translator)
        self.data_manager = ModellingDataManager(
            mapCanvas=self.iface.mapCanvas(), logger=self.log, project=QgsProject.instance()
        )
        self.model_manager = GeologicalModelManager()
        self.data_manager.set_model_manager(self.model_manager)

    def injectLogHandler(self):
        import logging

        import LoopStructural
        from loopstructural.toolbelt.log_handler import PlgLoggerHandler

        handler = PlgLoggerHandler(plg_logger_class=PlgLogger, push=True)
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

        LoopStructural.setLogging(level="warning", handler=handler)

    def initGui(self):
        """Set up plugin UI elements."""
        self.injectLogHandler()
        self.toolbar = self.iface.addToolBar(u'LoopStructural')
        self.toolbar.setObjectName(u'LoopStructural')
        # settings page within the QGIS preferences menu
        self.options_factory = PlgOptionsFactory()
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        # -- Actions
        self.action_help = QAction(
            QgsApplication.getThemeIcon("mActionHelpContents.svg"),
            self.tr("Help"),
            self.iface.mainWindow(),
        )
        self.action_help.triggered.connect(
            partial(QDesktopServices.openUrl, QUrl(__uri_homepage__))
        )

        self.action_settings = QAction(
            QgsApplication.getThemeIcon("console/iconSettingsConsole.svg"),
            self.tr("Settings"),
            self.iface.mainWindow(),
        )
        self.action_settings.triggered.connect(
            lambda: self.iface.showOptionsDialog(currentPage="mOptionsPage{}".format(__title__))
        )
        self.action_modelling = QAction(
            QIcon(os.path.dirname(__file__) + "/icon.png"),
            self.tr("LoopStructural Modelling"),
            self.iface.mainWindow(),
        )

        self.toolbar.addAction(self.action_modelling)

        # -- Menu
        self.iface.addPluginToMenu(__title__, self.action_settings)
        self.iface.addPluginToMenu(__title__, self.action_help)

        # -- Help menu

        # documentation
        self.iface.pluginHelpMenu().addSeparator()
        self.action_help_plugin_menu_documentation = QAction(
            QIcon(str(__icon_path__)),
            f"{__title__} - Documentation",
            self.iface.mainWindow(),
        )
        self.action_help_plugin_menu_documentation.triggered.connect(
            partial(QDesktopServices.openUrl, QUrl(__uri_homepage__))
        )

        self.iface.pluginHelpMenu().addAction(self.action_help_plugin_menu_documentation)

        ## --- dock widget
        self.loop_dockwidget = QDockWidget(self.tr("Loop"), self.iface.mainWindow())
        self.loop_widget = LoopWidget(
            self.iface.mainWindow(),
            mapCanvas=self.iface.mapCanvas(),
            logger=self.log,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
        )

        self.loop_dockwidget.setWidget(self.loop_widget)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.loop_dockwidget)
        right_docks = [
            d
            for d in self.iface.mainWindow().findChildren(QDockWidget)
            if self.iface.mainWindow().dockWidgetArea(d) == Qt.RightDockWidgetArea
        ]
        # If there are other dock widgets, tab this one with the first one found
        if right_docks:
            for dock in right_docks:
                if dock != self.loop_dockwidget:
                    self.iface.mainWindow().tabifyDockWidget(dock, self.loop_dockwidget)
                    # Optionally, bring your plugin tab to the front
                    self.loop_dockwidget.raise_()
                    break
        self.loop_dockwidget.show()

        self.loop_dockwidget.close()

        # -- Connect actions
        self.action_modelling.triggered.connect(self.loop_dockwidget.toggleViewAction().trigger)

    def tr(self, message: str) -> str:
        """Translate a string using Qt translation API.

        Parameters
        ----------
        message : str
            String to be translated.

        Returns
        -------
        str
            Translated version of the input string.
        """
        return QCoreApplication.translate(self.__class__.__name__, message)

    def unload(self):
        """Cleans up when plugin is disabled/uninstalled."""
        # -- Clean up menu
        self.iface.removePluginMenu(__title__, self.action_help)
        self.iface.removePluginMenu(__title__, self.action_settings)
        # self.iface.removeMenu(self.menu)
        # -- Clean up preferences panel in QGIS settings
        self.iface.unregisterOptionsWidgetFactory(self.options_factory)

        # remove from QGIS help/extensions menu
        if self.action_help_plugin_menu_documentation:
            self.iface.pluginHelpMenu().removeAction(self.action_help_plugin_menu_documentation)

        # remove actions
        del self.action_settings
        del self.action_help
        del self.toolbar

    def run(self):
        """Main process.

        :raises Exception: if there is no item in the feed
        """
        try:
            self.log(
                message=self.tr("Everything ran OK."),
                log_level=3,
                push=False,
            )
        except Exception as err:
            self.log(
                message=self.tr("Houston, we've got a problem: {}".format(err)),
                log_level=2,
                push=True,
            )
