#! python3

"""Main plugin module."""

# standard
import os
from functools import partial
from pathlib import Path

# PyQGIS
from qgis.core import QgsApplication, QgsSettings
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
from loopstructural.gui.dlg_settings import PlgOptionsFactory
from loopstructural.gui.modelling.modelling_widget import ModellingWidget as Modelling
from loopstructural.gui.visualisation.visualisation_widget import VisualisationWidget
from loopstructural.toolbelt import PlgLogger

# ############################################################################
# ########## Classes ###############
# ##################################


class LoopstructuralPlugin:
    def __init__(self, iface: QgisInterface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class which \
        provides the hook by which you can manipulate the QGIS application at run time.
        :type iface: QgsInterface
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

    def initGui(self):
        """Set up plugin UI elements."""
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
        self.action_visualisation = QAction(
            QIcon(os.path.dirname(__file__) + "/icon.png"),
            self.tr("LoopStructural Visualisation"),
            self.iface.mainWindow(),
        )
        self.toolbar.addAction(self.action_modelling)
        self.toolbar.addAction(self.action_visualisation)

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
        self.modelling_dockwidget = QDockWidget(self.tr("Modelling"), self.iface.mainWindow())
        self.model_setup_widget = Modelling(
            self.iface.mainWindow(), mapCanvas=self.iface.mapCanvas(), logger=self.log
        )
        self.modelling_dockwidget.setWidget(self.model_setup_widget)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.modelling_dockwidget)
        right_docks = [
            d
            for d in self.iface.mainWindow().findChildren(QDockWidget)
            if self.iface.mainWindow().dockWidgetArea(d) == Qt.RightDockWidgetArea
        ]
        # If there are other dock widgets, tab this one with the first one found
        if right_docks:
            for dock in right_docks:
                if dock != self.modelling_dockwidget:
                    self.iface.mainWindow().tabifyDockWidget(dock, self.modelling_dockwidget)
                    # Optionally, bring your plugin tab to the front
                    self.modelling_dockwidget.raise_()
                    break
        self.modelling_dockwidget.show()

        self.modelling_dockwidget.close()

        ## -- visualisation dock widget
        self.visualisation_dockwidget = QDockWidget(
            self.tr("Visualisation"), self.iface.mainWindow()
        )
        self.visualisation_widget = VisualisationWidget(
            self.iface.mainWindow(), mapCanvas=self.iface.mapCanvas(), logger=self.log
        )
        self.visualisation_dockwidget.setWidget(self.visualisation_widget)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.visualisation_dockwidget)
        right_docks = [
            d
            for d in self.iface.mainWindow().findChildren(QDockWidget)
            if self.iface.mainWindow().dockWidgetArea(d) == Qt.RightDockWidgetArea
        ]
        # If there are other dock widgets, tab this one with the first one found
        if right_docks:
            for dock in right_docks:
                if dock != self.visualisation_dockwidget:
                    self.iface.mainWindow().tabifyDockWidget(dock, self.visualisation_dockwidget)
                    # Optionally, bring your plugin tab to the front
                    self.visualisation_dockwidget.raise_()
                    break
        self.visualisation_dockwidget.show()
        self.visualisation_dockwidget.close()

        # -- Connect actions
        self.action_modelling.triggered.connect(
            self.modelling_dockwidget.toggleViewAction().trigger
        )
        self.action_visualisation.triggered.connect(
            self.visualisation_dockwidget.toggleViewAction().trigger
        )

    def tr(self, message: str) -> str:
        """Get the translation for a string using Qt translation API.

        :param message: string to be translated.
        :type message: str

        :returns: Translated version of message.
        :rtype: str
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
