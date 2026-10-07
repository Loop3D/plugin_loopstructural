"""The pages of the steps of the modelling dock.

Each page has a `check()` method. It returns the `StepCheck` of the step.
The existing tabs and dialogs are the contents of the pages.
"""

from qgis.core import Qgis, QgsApplication
from qgis.gui import QgsMessageBar
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.map2loop_tools import launchers
from loopstructural.gui.modelling.fault_adjacency_tab import FaultAdjacencyTab
from loopstructural.gui.modelling.geological_history_tab import GeologialHistoryTab
from loopstructural.gui.modelling.geological_model_tab import GeologicalModelTab
from loopstructural.gui.modelling.model_definition import ModelDefinitionTab
from loopstructural.gui.modelling.model_definition.fault_layers import FaultLayersWidget
from loopstructural.gui.modelling.model_definition.stratigraphic_layers import (
    StratigraphicLayersWidget,
)

from loopstructural.main import layer_roles
from loopstructural.main.fault_topology_calc import (
    FaultTopologyError,
    calculate_from_data_manager,
    result_message,
)
from loopstructural.main.workflow_mode import WORKFLOW_MODE_LABELS, WORKFLOW_MODES

from . import checks
from .export_panel import ExportPanel
from .section_stack import SectionStack, page_scroll_area


class StepPage(QWidget):
    """Base class of the pages: a key, the managers and a check function."""

    key = None

    def __init__(self, parent=None, *, data_manager=None, model_manager=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.model_manager = model_manager

    def check(self):
        """Return the `StepCheck` of this step."""
        return checks.STEP_CHECKS[self.key](self.data_manager, self.model_manager)

    def _show_tool(self, tool):
        launchers.show_tool_dialog(tool, self, data_manager=self.data_manager)

    def _tool_button(self, text, icon, tooltip, actions):
        """Return a button with a menu. ``actions`` are ``(text, tool)`` pairs."""
        menu = QMenu(self)
        for action_text, tool in actions:
            menu.addAction(action_text, lambda _checked=False, t=tool: self._show_tool(t))
        button = QToolButton(self)
        button.setText(text)
        button.setIcon(icon)
        button.setToolTip(tooltip)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        return button


class DataStep(StepPage):
    """Step 1: the bounding box, the CRS and the DEM."""

    key = checks.STEP_DATA

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        convert = QPushButton("Convert data...", self)
        convert.setIcon(QgsApplication.getThemeIcon('mActionSharingImport.svg'))
        convert.setToolTip("Convert the columns of your map data to the names that the tools use.")
        convert.clicked.connect(lambda _checked=False: self._show_tool(launchers.DATA_CONVERSION))
        row = QHBoxLayout()
        row.addWidget(QLabel("Select the area and the elevation.", self), 1)
        row.addWidget(convert)
        layout.addLayout(row)

        # The start choice. The "constraints" choice hides steps 2 and 3.
        self.mode_combo = QComboBox(self)
        for mode in WORKFLOW_MODES:
            self.mode_combo.addItem(WORKFLOW_MODE_LABELS[mode], mode)
        self.mode_combo.setToolTip(
            "Steps 2 and 3 make features and constraints from a geological map. "
            "Interpolate from constraints hides them. Change the choice to show them again."
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Method:", self))
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)
        self.tab = ModelDefinitionTab(self, data_manager=self.data_manager)
        layout.addWidget(page_scroll_area(self.tab, self), 1)

    def set_workflow_mode(self, mode):
        index = self.mode_combo.findData(mode)
        if index >= 0 and index != self.mode_combo.currentIndex():
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(index)
            self.mode_combo.blockSignals(False)

    def _on_mode_changed(self, _index):
        if self.data_manager is not None:
            self.data_manager.set_workflow_mode(self.mode_combo.currentData())


class StratigraphyStep(StepPage):
    """Step 2: the source layers, the stratigraphic column and the results from the map."""

    key = checks.STEP_STRATIGRAPHY

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tab = GeologialHistoryTab(self, data_manager=self.data_manager)

        # More ways to build the column, in the "Build column" menu of the column
        build_menu = self.tab.stratigraphic_column_widget.buildMenu
        build_menu.addSeparator()
        build_menu.addAction(
            "Sort automatically...", lambda: self._show_tool(launchers.SORTER)
        ).setToolTip("Calculate the order of the units from the map.")
        build_menu.addAction(
            "Define the order by hand...", lambda: self._show_tool(launchers.USER_SORTER)
        )
        build_menu.addAction(
            "Paint the order on the map...", lambda: self._show_tool(launchers.PAINT_STRAT_ORDER)
        ).setToolTip("Show the order of the column on the geology polygons.")

        # The source layers are a section of the column stack, so the page has
        # at most two open sections and one scroll area.
        self.stratigraphy_layers = StratigraphicLayersWidget(self, self.data_manager)
        sections = self.tab.stratigraphic_column_widget.sections
        sections.add_section(
            self.stratigraphy_layers,
            'layers',
            'Stratigraphic layers',
            summary=self._layers_summary,
            collapsed=self._layers_are_set(),
            index=1,
        )

        derive = self._tool_button(
            "Derive from map",
            QgsApplication.getThemeIcon('mActionSharingExport.svg'),
            "Calculate data from the geology map and the column.",
            [
                ("Extract basal contacts...", launchers.BASAL_CONTACTS),
                ("Calculate thickness...", launchers.THICKNESS),
                ("Sample the contacts...", launchers.SAMPLER),
            ],
        )
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(derive)
        layout.addLayout(row)
        layout.addWidget(page_scroll_area(self.tab, self), 1)

    def _layers_are_set(self):
        """The section starts collapsed after the first setup."""
        if self.data_manager is None:
            return False
        return self.data_manager.get_layer_role(layer_roles.STRUCTURE) is not None

    def _layers_summary(self):
        if self.data_manager is None:
            return ""
        roles = self.data_manager.layer_roles
        role = (
            layer_roles.GEOLOGY
            if roles.contacts_source == layer_roles.CONTACTS_FROM_GEOLOGY
            else layer_roles.BASAL_CONTACTS
        )
        parts = []
        for value in (self.data_manager.get_layer_role(role), roles.get(layer_roles.STRUCTURE)):
            if value is not None:
                parts.append(value.name() if hasattr(value, 'name') else str(value))
        return ", ".join(parts) if parts else "not selected"


class FaultsStep(StepPage):
    """Step 3: the fault layer, the fault topology and the adjacency tables."""

    key = checks.STEP_FAULTS

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.fault_layers = FaultLayersWidget(self, self.data_manager)
        self.sections = SectionStack(self, 'faults', self.data_manager)
        self.sections.add_section(
            self.fault_layers, 'fault_layer', 'Fault layer', summary=self._fault_layer_summary
        )
        layout.addWidget(self.sections)

        self.message_bar = QgsMessageBar(self)
        layout.addWidget(self.message_bar)

        self.topology_button = QPushButton("Calculate topology", self)
        self.topology_button.clicked.connect(self._calculate_topology)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.topology_button)
        layout.addLayout(row)
        # The button follows the fault layer and the name field
        self.fault_layers.faultTraceLayer.layerChanged.connect(self.update_topology_button)
        self.fault_layers.faultNameField.fieldChanged.connect(self.update_topology_button)
        if self.data_manager is not None:
            self.data_manager.layer_roles.attach(lambda _role, _value: self.update_topology_button())
        self.update_topology_button()

        self.adjacency = FaultAdjacencyTab(self, data_manager=self.data_manager)
        layout.addWidget(page_scroll_area(self.adjacency, self), 1)

    def _fault_traces(self):
        traces = self.data_manager.get_fault_traces() if self.data_manager is not None else None
        return traces or {}

    def update_topology_button(self, *_args):
        """Enable the button when the fault layer and the name field are set."""
        traces = self._fault_traces()
        layer = self.data_manager.get_layer_role(layer_roles.FAULT_TRACES) if self.data_manager else None
        if layer is None or not traces.get('fault_name_field'):
            self.topology_button.setEnabled(False)
            self.topology_button.setToolTip(
                "Select a fault layer and the field with the fault name in the Fault layer section."
            )
        else:
            self.topology_button.setEnabled(True)
            self.topology_button.setToolTip(
                "Find which faults touch each other, from the fault traces."
            )

    def _calculate_topology(self):
        self.message_bar.clearWidgets()
        try:
            result = calculate_from_data_manager(self.data_manager)
        except FaultTopologyError as error:
            self.message_bar.pushMessage("Fault topology", str(error), level=Qgis.MessageLevel.Critical)
            return
        text, warn = result_message(result)
        self.message_bar.pushMessage(
            "Fault topology",
            text,
            level=Qgis.MessageLevel.Warning if warn else Qgis.MessageLevel.Success,
            duration=0 if warn else 8,
        )

    def _fault_layer_summary(self):
        if self.data_manager is None:
            return ""
        layer = self.data_manager.get_layer_role(layer_roles.FAULT_TRACES)
        if layer is None:
            return "not selected"
        return layer.name() if hasattr(layer, 'name') else str(layer)


class ModelStep(StepPage):
    """Step 4: the features, their constraints and the build of the model."""

    key = checks.STEP_MODEL

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tab = GeologicalModelTab(
            self, model_manager=self.model_manager, data_manager=self.data_manager
        )
        layout.addWidget(self.tab)


class ViewStep(StepPage):
    """Step 5: the 3D view and the export of the results.

    In one dock, the visualisation widget is in this page. With separate docks,
    the page has a button that shows the visualisation dock.
    """

    key = checks.STEP_VIEW
    open_view_requested = pyqtSignal()

    def __init__(self, parent=None, *, view_widget=None, **kwargs):
        super().__init__(parent, **kwargs)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view_widget = view_widget
        if view_widget is not None:
            layout.addWidget(view_widget)
        else:
            label = QLabel("The 3D view is in its own dock.", self)
            label.setWordWrap(True)
            button = QPushButton("Open 3D view", self)
            button.setIcon(QgsApplication.getThemeIcon('mActionShowAllLayers.svg'))
            button.clicked.connect(lambda _checked=False: self.open_view_requested.emit())
            layout.addWidget(label)
            layout.addWidget(button)
            layout.addStretch(1)
        self.export_panel = ExportPanel(
            self, model_manager=self.model_manager, data_manager=self.data_manager
        )
        layout.addWidget(self.export_panel)

    def refresh(self):
        """Enable the exports when the model is solved."""
        state = self.model_manager.model_state if self.model_manager is not None else 'empty'
        self.export_panel.set_model_solved(state == 'solved')
