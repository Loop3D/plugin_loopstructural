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
from loopstructural.debug_manager import DebugManager
from loopstructural.gui.dlg_settings import PlgOptionsFactory
from loopstructural.gui.loop_widget import LoopWidget
from loopstructural.main.data_manager import ModellingDataManager
from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.processing import (
    Map2LoopProvider,
)
from loopstructural.toolbelt import PlgLogger, PlgOptionsManager

# ############################################################################
# ########## Classes ###############
# ##################################


class LoopstructuralPlugin:
    """QGIS plugin entrypoint for LoopStructural.

    This class initializes plugin resources, UI elements and data/model managers
    required for LoopStructural integration with QGIS.
    """

    def __init__(self, iface: QgisInterface):
        """Initialize the plugin.

        Parameters
        ----------
        iface : QgisInterface
            An interface instance provided by QGIS which allows the plugin to
            manipulate the QGIS application at run time.
        """
        self.iface = iface
        self.log = PlgLogger().log
        self.debug_manager = DebugManager(plugin=self)

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
        """Install LoopStructural logging handler that forwards logs to the plugin logger.

        This configures LoopStructural's logging to use the plugin's
        PlgLoggerHandler so log records are captured and forwarded to the
        plugin's logging infrastructure.
        """
        import logging

        from map2loop.logging import setLogging as setLogging_m2l

        import LoopStructural
        from loopstructural.toolbelt.log_handler import PlgLoggerHandler

        handler = PlgLoggerHandler(plg_logger_class=PlgLogger, push=True)
        handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))

        LoopStructural.setLogging(level="warning", handler=handler)
        setLogging_m2l(level="warning", handler=handler)

    def initGui(self):
        """Set up plugin UI elements."""
        self.injectLogHandler()
        self.toolbar = self.iface.addToolBar(u'LoopStructural')
        self.toolbar.setObjectName(u'LoopStructural')
        # settings page within the QGIS preferences menu
        self.options_factory = PlgOptionsFactory()
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        # -- Actions
        self.action_fault_topology = QAction(
            "Fault Topology Calculator",
            self.iface.mainWindow(),
        )
        self.action_fault_topology.triggered.connect(self.show_fault_topology_dialog)
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
        self.action_data_conversion = QAction(
            self.tr("LoopStructural Data Conversion"),
            self.iface.mainWindow(),
        )
        self.action_data_conversion.triggered.connect(self.show_data_conversion_dialog)
        self.action_visualisation = QAction(
            QIcon(os.path.dirname(__file__) + "/3D_icon.png"),
            self.tr("LoopStructural Visualisation"),
            self.iface.mainWindow(),
        )

        self.toolbar.addAction(self.action_modelling)
        self.toolbar.addAction(self.action_data_conversion)
        self.toolbar.addAction(self.action_fault_topology)
        # -- Menu
        self.iface.addPluginToMenu(__title__, self.action_settings)
        self.iface.addPluginToMenu(__title__, self.action_help)
        self.iface.addPluginToMenu(__title__, self.action_data_conversion)
        self.initProcessing()

        # Map2Loop tool actions
        self.action_sampler = QAction(
            "Sampler",
            self.iface.mainWindow(),
        )
        self.action_sampler.triggered.connect(self.show_sampler_dialog)

        self.action_sorter = QAction(
            QIcon(
                os.path.dirname(__file__) + "/resources/images/automatic_stratigraphic_column.png"
            ),
            "Automatic Stratigraphic Sorter",
            self.iface.mainWindow(),
        )
        self.action_sorter.triggered.connect(self.show_sorter_dialog)

        self.action_user_sorter = QAction(
            QIcon(os.path.dirname(__file__) + "/resources/images/stratigraphic_column.png"),
            "User-Defined Stratigraphic Column",
            self.iface.mainWindow(),
        )
        self.action_user_sorter.triggered.connect(self.show_user_sorter_dialog)

        self.action_basal_contacts = QAction(
            QIcon(os.path.dirname(__file__) + "/resources/images/basal_contacts.png"),
            "Extract Basal Contacts",
            self.iface.mainWindow(),
        )
        self.action_basal_contacts.triggered.connect(self.show_basal_contacts_dialog)

        self.action_thickness = QAction(
            "Thickness Calculator",
            self.iface.mainWindow(),
        )
        self.action_thickness.triggered.connect(self.show_thickness_dialog)

        self.action_paint_strat_order = QAction(
            "Paint Stratigraphic Order",
            self.iface.mainWindow(),
        )
        self.action_paint_strat_order.triggered.connect(self.show_paint_strat_order_dialog)

        # Add all map2loop tool actions to the toolbar
        self.toolbar.addAction(self.action_sampler)
        self.toolbar.addAction(self.action_sorter)
        self.toolbar.addAction(self.action_user_sorter)
        self.toolbar.addAction(self.action_basal_contacts)
        self.toolbar.addAction(self.action_thickness)
        self.toolbar.addAction(self.action_paint_strat_order)
        self.toolbar.addAction(self.action_fault_topology)

        self.iface.addPluginToMenu(__title__, self.action_sampler)
        self.iface.addPluginToMenu(__title__, self.action_sorter)
        self.iface.addPluginToMenu(__title__, self.action_user_sorter)
        self.iface.addPluginToMenu(__title__, self.action_basal_contacts)
        self.iface.addPluginToMenu(__title__, self.action_thickness)
        self.iface.addPluginToMenu(__title__, self.action_paint_strat_order)
        self.iface.addPluginToMenu(__title__, self.action_fault_topology)

        self.initProcessing()

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
        # Get the setting for separate dock widgets
        settings = PlgOptionsManager.get_plg_settings()

        if settings.separate_dock_widgets:
            # Create separate dock widgets for modelling and visualisation
            self.loop_widget = LoopWidget(
                self.iface.mainWindow(),
                mapCanvas=self.iface.mapCanvas(),
                logger=self.log,
                data_manager=self.data_manager,
                model_manager=self.model_manager,
            )
            self.toolbar.addAction(self.action_visualisation)

            # Create modelling dock
            self.modelling_dockwidget = QDockWidget(
                self.tr("Loop - Modelling"), self.iface.mainWindow()
            )
            self.modelling_dockwidget.setWidget(self.loop_widget.get_modelling_widget())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.modelling_dockwidget)

            # Create visualisation dock
            self.visualisation_dockwidget = QDockWidget(
                self.tr("Loop - Visualisation"), self.iface.mainWindow()
            )
            self.visualisation_dockwidget.setWidget(self.loop_widget.get_visualisation_widget())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.visualisation_dockwidget)

            # Tab them with other right docks if available
            right_docks = [
                d
                for d in self.iface.mainWindow().findChildren(QDockWidget)
                if self.iface.mainWindow().dockWidgetArea(d) == Qt.RightDockWidgetArea
            ]
            if right_docks:
                for dock in right_docks:
                    if dock != self.modelling_dockwidget and dock != self.visualisation_dockwidget:
                        self.iface.mainWindow().tabifyDockWidget(dock, self.modelling_dockwidget)
                        self.modelling_dockwidget.raise_()
                        break

            # Tab visualisation with modelling
            self.iface.mainWindow().tabifyDockWidget(
                self.modelling_dockwidget, self.visualisation_dockwidget
            )

            self.modelling_dockwidget.show()
            self.visualisation_dockwidget.show()
            self.modelling_dockwidget.close()
            self.visualisation_dockwidget.close()

            # Connect action to toggle modelling dock
            self.action_modelling.triggered.connect(
                self.modelling_dockwidget.toggleViewAction().trigger
            )
            self.action_visualisation.triggered.connect(
                self.visualisation_dockwidget.toggleViewAction().trigger
            )
            # Store reference to main dock as None for unload compatibility
            self.loop_dockwidget = None
        else:
            # Create single dock widget with tabs (default behavior)
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

            # Store references to separate docks as None for unload compatibility
            self.modelling_dockwidget = None
            self.visualisation_dockwidget = None

    def show_sampler_dialog(self):
        """Show the sampler dialog."""
        from loopstructural.gui.map2loop_tools import SamplerDialog

        dialog = SamplerDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_data_conversion_dialog(self):
        """Show the data conversion dialog."""
        from loopstructural.gui.data_conversion import AutomaticConversionDialog

        dialog = AutomaticConversionDialog(
            self.iface.mainWindow(),
            project=self.data_manager.project if self.data_manager else None,
        )
        dialog.exec_()

    def show_sorter_dialog(self):
        """Show the automatic stratigraphic sorter dialog."""
        from loopstructural.gui.map2loop_tools import SorterDialog

        dialog = SorterDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_user_sorter_dialog(self):
        """Show the user-defined stratigraphic column dialog."""
        from loopstructural.gui.map2loop_tools import UserDefinedSorterDialog

        dialog = UserDefinedSorterDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_basal_contacts_dialog(self):
        """Show the basal contacts extractor dialog."""
        from loopstructural.gui.map2loop_tools import BasalContactsDialog

        dialog = BasalContactsDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_thickness_dialog(self):
        """Show the thickness calculator dialog."""
        from loopstructural.gui.map2loop_tools import ThicknessCalculatorDialog

        dialog = ThicknessCalculatorDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_paint_strat_order_dialog(self):
        """Show the paint stratigraphic order dialog."""
        from loopstructural.gui.map2loop_tools import PaintStratigraphicOrderDialog

        dialog = PaintStratigraphicOrderDialog(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

    def show_fault_topology_dialog(self):
        """Show the fault topology calculator dialog."""
        from loopstructural.gui.map2loop_tools.fault_topology_widget import FaultTopologyWidget

        dialog = FaultTopologyWidget(
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        dialog.exec_()

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

    def initProcessing(self):
        """Initialize the processing provider."""
        self.provider = Map2LoopProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        """Clean up when plugin is disabled or uninstalled.

        This implementation is defensive: initGui may not have been run when
        QGIS asks the plugin to unload (plugin reloader), so attributes may be
        missing. Use getattr to check for presence and guard removals/deletions.
        """
        # -- Clean up dock widgets
        for dock_attr in ("loop_dockwidget", "modelling_dockwidget", "visualisation_dockwidget"):
            dock = getattr(self, dock_attr, None)
            if dock:
                try:
                    self.iface.removeDockWidget(dock)
                except Exception:
                    # ignore errors during unload
                    pass
                try:
                    delattr(self, dock_attr)
                except Exception:
                    pass

        # -- Clean up menu/actions (only remove if they exist)
        for attr in (
            "action_help",
            "action_settings",
            "action_data_conversion",
            "action_sampler",
            "action_sorter",
            "action_user_sorter",
            "action_basal_contacts",
            "action_thickness",
            "action_paint_strat_order",
            "action_fault_topology",
            "action_modelling",
            "action_visualisation",
        ):
            act = getattr(self, attr, None)
            if act:
                try:
                    self.iface.removePluginMenu(__title__, act)
                except Exception:
                    pass
                try:
                    delattr(self, attr)
                except Exception:
                    pass

        # -- Clean up preferences panel in QGIS settings
        options_factory = getattr(self, "options_factory", None)
        if options_factory:
            try:
                self.iface.unregisterOptionsWidgetFactory(options_factory)
            except Exception:
                pass
            try:
                delattr(self, "options_factory")
            except Exception:
                pass

        # -- Unregister processing provider
        provider = getattr(self, "provider", None)
        if provider:
            try:
                QgsApplication.processingRegistry().removeProvider(provider)
            except Exception:
                pass
            try:
                delattr(self, "provider")
            except Exception:
                pass

        # remove from QGIS help/extensions menu
        help_action = getattr(self, "action_help_plugin_menu_documentation", None)
        if help_action:
            try:
                self.iface.pluginHelpMenu().removeAction(help_action)
            except Exception:
                pass
            try:
                delattr(self, "action_help_plugin_menu_documentation")
            except Exception:
                pass

        # remove toolbar if present
        if getattr(self, "toolbar", None):
            try:
                # There's no explicit removeToolbar API; deleting reference is fine.
                delattr(self, "toolbar")
            except Exception:
                pass
