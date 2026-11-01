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
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QMenu

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
from loopstructural.gui.map2loop_tools import launchers
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
        self.model_manager = GeologicalModelManager(debug_manager=self.debug_manager)
        self.data_manager.set_model_manager(self.model_manager)
        self.data_manager.set_debug_manager(self.debug_manager)

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
        handler.setLevel(logging.WARNING)

        # Threshold is re-read from settings on every record rather than fixed
        # at startup, so toggling debug_mode in the plugin options immediately
        # surfaces LoopStructural's per-feature/per-coordinate build/solve
        # logging (logger.info(...) in its builders) -- the most direct way to
        # see which feature "Solve Model" is currently stuck on.
        def _current_threshold():
            try:
                if PlgOptionsManager.get_plg_settings().debug_mode:
                    return logging.INFO
            except Exception:
                pass
            return logging.WARNING

        # LoopStructural 1.7 replaced global handler rewiring with add_sink():
        # LoopStructural.setLogging() only rewires loggers that already exist
        # at call time, so LoopStructural.getLogger() calls made later (e.g.
        # lazily-imported GUI modules) never picked up our handler. add_sink()
        # registers the sink so every logger created afterwards forwards to it too.
        def _forward_to_handler(record):
            if record.levelno < _current_threshold():
                return
            # Only pop up a message-bar toast for warnings/errors; the debug-mode
            # INFO chatter (one message per feature/coordinate) would otherwise
            # spam a toast per step. It's still visible in the Log Messages panel.
            handler.push = record.levelno >= logging.WARNING
            handler.emit(record)

        LoopStructural.add_sink(_forward_to_handler)
        setLogging_m2l(level="warning", handler=handler)

    def initGui(self):
        """Set up plugin UI elements."""
        self.injectLogHandler()
        self.toolbar = self.iface.addToolBar('LoopStructural')
        self.toolbar.setObjectName('LoopStructural')
        # settings page within the QGIS preferences menu
        self.options_factory = PlgOptionsFactory()
        self.iface.registerOptionsWidgetFactory(self.options_factory)

        # -- Actions
        self.action_fault_topology = QAction(
            self.tr("Fault Topology Calculator"),
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
            lambda: self.iface.showOptionsDialog(currentPage=f"mOptionsPage{__title__}")
        )
        self.action_modelling = QAction(
            QIcon(os.path.dirname(__file__) + "/icon.png"),
            self.tr("LoopStructural"),
            self.iface.mainWindow(),
        )
        self.action_data_conversion = QAction(
            self.tr("LoopStructural Data Conversion"),
            self.iface.mainWindow(),
        )
        self.action_data_conversion.triggered.connect(self.show_data_conversion_dialog)
        self.action_visualisation = QAction(
            QIcon(os.path.dirname(__file__) + "/3D_icon.png"),
            self.tr("3D View"),
            self.iface.mainWindow(),
        )

        # -- Toolbar: the dock, the 3D view and the help
        self.toolbar.addAction(self.action_modelling)
        self.toolbar.addAction(self.action_visualisation)
        self.toolbar.addAction(self.action_help)
        # -- Menu
        self.iface.addPluginToMenu(__title__, self.action_modelling)
        self.iface.addPluginToMenu(__title__, self.action_visualisation)
        self.iface.addPluginToMenu(__title__, self.action_settings)
        self.iface.addPluginToMenu(__title__, self.action_help)
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

        # The tools are in the steps of the dock. The "Tools" submenu has them
        # for the advanced users.
        self.tools_menu = QMenu(self.tr("Tools"), self.iface.mainWindow())
        for action in (
            self.action_data_conversion,
            self.action_sorter,
            self.action_user_sorter,
            self.action_paint_strat_order,
            self.action_basal_contacts,
            self.action_thickness,
            self.action_sampler,
            self.action_fault_topology,
        ):
            self.tools_menu.addAction(action)
        self.action_tools = self.tools_menu.menuAction()
        self.iface.addPluginToMenu(__title__, self.action_tools)

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
                separate_docks=True,
            )

            # Create modelling dock
            self.modelling_dockwidget = QDockWidget(
                self.tr("Loop - Modelling"), self.iface.mainWindow()
            )
            self.modelling_dockwidget.setWidget(self.loop_widget.get_modelling_widget())
            self.iface.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.modelling_dockwidget
            )

            # Create visualisation dock
            self.visualisation_dockwidget = QDockWidget(
                self.tr("Loop - Visualisation"), self.iface.mainWindow()
            )
            self.visualisation_dockwidget.setWidget(self.loop_widget.get_visualisation_widget())
            self.iface.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.visualisation_dockwidget
            )

            # Tab them with other right docks if available
            right_docks = [
                d
                for d in self.iface.mainWindow().findChildren(QDockWidget)
                if self.iface.mainWindow().dockWidgetArea(d)
                == Qt.DockWidgetArea.RightDockWidgetArea
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
            # The last step of the modelling dock has a button for the 3D view
            self.loop_widget.get_modelling_widget().open_view_requested.connect(
                self._show_visualisation_dock
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
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.loop_dockwidget)
            right_docks = [
                d
                for d in self.iface.mainWindow().findChildren(QDockWidget)
                if self.iface.mainWindow().dockWidgetArea(d)
                == Qt.DockWidgetArea.RightDockWidgetArea
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
            self.action_visualisation.triggered.connect(self._show_view_step)

            # Store references to separate docks as None for unload compatibility
            self.modelling_dockwidget = None
            self.visualisation_dockwidget = None

    def _show_visualisation_dock(self):
        """Show the visualisation dock (when the docks are separate)."""
        self.visualisation_dockwidget.show()
        self.visualisation_dockwidget.raise_()

    def _show_view_step(self):
        """Show the dock with the last step, which has the 3D view."""
        self.loop_dockwidget.show()
        self.loop_dockwidget.raise_()
        self.loop_widget.show_view_step()

    def _show_tool(self, tool):
        launchers.show_tool_dialog(
            tool,
            self.iface.mainWindow(),
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )

    def show_sampler_dialog(self):
        """Show the sampler dialog."""
        self._show_tool(launchers.SAMPLER)

    def show_data_conversion_dialog(self):
        """Show the data conversion dialog."""
        self._show_tool(launchers.DATA_CONVERSION)

    def show_sorter_dialog(self):
        """Show the automatic stratigraphic sorter dialog."""
        self._show_tool(launchers.SORTER)

    def show_user_sorter_dialog(self):
        """Show the user-defined stratigraphic column dialog."""
        self._show_tool(launchers.USER_SORTER)

    def show_basal_contacts_dialog(self):
        """Show the basal contacts extractor dialog."""
        self._show_tool(launchers.BASAL_CONTACTS)

    def show_thickness_dialog(self):
        """Show the thickness calculator dialog."""
        self._show_tool(launchers.THICKNESS)

    def show_paint_strat_order_dialog(self):
        """Show the paint stratigraphic order dialog."""
        self._show_tool(launchers.PAINT_STRAT_ORDER)

    def show_fault_topology_dialog(self):
        """Show the fault topology calculator dialog."""
        self._show_tool(launchers.FAULT_TOPOLOGY)

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
            "action_tools",
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

        tools_menu = getattr(self, "tools_menu", None)
        if tools_menu:
            try:
                tools_menu.deleteLater()
            except Exception:
                pass
            try:
                delattr(self, "tools_menu")
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
