#! python3
"""Main Loop widget used in the plugin dock.

This module exposes `LoopWidget` which provides the primary user
interface for interacting with LoopStructural features inside QGIS.
"""

from qgis.PyQt.QtWidgets import QVBoxLayout, QWidget

from .modelling.modelling_widget import ModellingWidget
from .modelling.steps import checks
from .visualisation.visualisation_widget import VisualisationWidget


class LoopWidget(QWidget):
    """Main dock widget that contains modelling and visualisation tools.

    The widget has the steps of the modelling workflow. The last step is the
    3D view. With ``separate_docks``, the 3D view is a widget for its own dock,
    and the last step has a button that opens that dock.
    """

    def __init__(
        self,
        parent=None,
        *,
        mapCanvas=None,
        logger=None,
        data_manager=None,
        model_manager=None,
        separate_docks=False,
    ):
        """Initialize the Loop widget.

        Parameters
        ----------
        separate_docks : bool
            If True, the visualisation widget is not in the steps. The caller
            puts it in its own dock.
        """
        super().__init__(parent)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = data_manager
        self.model_manager = model_manager

        self.visualisation_widget = VisualisationWidget(
            self,
            mapCanvas=self.mapCanvas,
            logger=self.logger,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
        )
        self.modelling_widget = ModellingWidget(
            self,
            mapCanvas=self.mapCanvas,
            logger=self.logger,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
            view_widget=None if separate_docks else self.visualisation_widget,
        )

        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.addWidget(self.modelling_widget)

    def show_view_step(self):
        """Go to the last step, which has the 3D view."""
        self.modelling_widget.show_step(checks.STEP_VIEW)

    def get_modelling_widget(self):
        """Return the modelling widget instance.

        Returns
        -------
        ModellingWidget
            The modelling widget.
        """
        return self.modelling_widget

    def get_visualisation_widget(self):
        """Return the visualisation widget instance.

        Returns
        -------
        VisualisationWidget
            The visualisation widget.
        """
        return self.visualisation_widget
