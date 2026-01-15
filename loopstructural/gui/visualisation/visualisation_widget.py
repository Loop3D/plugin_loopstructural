from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .loop_pyvistaqt_wrapper import LoopPyVistaQTPlotter
from .object_list_widget import ObjectListWidget
from .feature_list_widget import FeatureListWidget
from .object_properties_widget import ObjectPropertiesWidget


class VisualisationWidget(QWidget):
    def __init__(self, parent: QWidget = None, mapCanvas=None, logger=None, model_manager=None):

        super().__init__(parent)
        # Load the UI file for Tab 1
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.model_manager = model_manager

        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)

        # Create a splitter to separate the viewer and the object list
        splitter = QSplitter(self)
        mainLayout.addWidget(splitter)

        # Create the object selection sidebar

        # Create the viewer
        self.plotter = LoopPyVistaQTPlotter(parent)
        # self.plotter.add_axes()
        self.objectPropertiesWidget = ObjectPropertiesWidget(viewer=self.plotter)

        self.objectList = ObjectListWidget(viewer=self.plotter,properties_widget=self.objectPropertiesWidget)

        # Modify layout to stack object list and feature list vertically
        sidebarSplitter = QSplitter(Qt.Vertical, self)
        sidebarSplitter.addWidget(self.objectList)

        # Create the feature list widget
        self.featureList = FeatureListWidget(model_manager=self.model_manager, viewer=self.plotter)
        sidebarSplitter.addWidget(self.featureList)
        splitter.addWidget(sidebarSplitter)
        splitter.addWidget(self.plotter)
        # Add properties panel but start it collapsed (size 0)
        splitter.addWidget(self.objectPropertiesWidget)
        self._main_splitter = splitter
        # initial sizes: sidebar, main, properties (collapsed)
        splitter.setSizes([200, 600, 0])
        # remember previous sizes so we can restore when blocking expansion
        self._previous_splitter_sizes = splitter.sizes()
        # Intercept user splitter moves to prevent expanding properties panel when not allowed
        try:
            splitter.splitterMoved.connect(self._on_splitter_moved)
        except Exception:
            pass

    def show_properties_panel(self, show: bool):
        """Expand or collapse the properties panel in the splitter.

        When collapsed we set its size to 0 so it can't be opened accidentally.
        """
        if not hasattr(self, '_main_splitter'):
            return
        sizes = self._main_splitter.sizes()
        # sizes: [sidebar, main, properties]
        if show:
            # restore a modest width for properties panel, clamp values
            sidebar = max(150, sizes[0])
            main = max(300, sizes[1])
            prop = 250
            self._main_splitter.setSizes([sidebar, main, prop])
            self._previous_splitter_sizes = [sidebar, main, prop]
        else:
            # collapse properties to 0 width
            self._main_splitter.setSizes([sizes[0], sizes[1], 0])
            self._previous_splitter_sizes = [sizes[0], sizes[1], 0]

    def is_properties_panel_visible(self) -> bool:
        if not hasattr(self, '_main_splitter'):
            return False
        return self._main_splitter.sizes()[2] > 0

    def _can_show_properties(self) -> bool:
        """Return True when properties panel may be shown (e.g. an object selected)."""
        try:
            w = self.objectPropertiesWidget
            return getattr(w, 'current_object_name', None) is not None
        except Exception:
            return False

    def _on_splitter_moved(self, pos: int, index: int):
        """Handler called after the user moves the splitter handle.

        If the user tries to open the properties panel (third pane) but
        _can_show_properties() is False, silently restore the previous sizes
        to block expansion.
        """
        try:
            sizes = self._main_splitter.sizes()
            # if properties width > 0 and we are not allowed to show it, restore
            if sizes[2] > 0 and not self._can_show_properties():
                # restore previous sizes
                self._main_splitter.blockSignals(True)
                self._main_splitter.setSizes(self._previous_splitter_sizes)
                self._main_splitter.blockSignals(False)
            else:
                # update remembered sizes for later
                self._previous_splitter_sizes = sizes
        except Exception:
            pass
