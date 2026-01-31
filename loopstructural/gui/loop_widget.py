#! python3
"""Main Loop widget used in the plugin dock.

This module exposes `LoopWidget` which provides the primary user
interface for interacting with LoopStructural features inside QGIS.
"""

from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .modelling.modelling_widget import ModellingWidget
from .visualisation.visualisation_widget import VisualisationWidget


class LoopWidget(QWidget):
    """Main dock widget that contains modelling and visualisation tools.

    The widget composes multiple tabs and controls used to construct and
    inspect geological models.
    """

    def __init__(
        self, parent=None, *, mapCanvas=None, logger=None, data_manager=None, model_manager=None
    ):
        """Initialize the Loop widget.

        Parameters
        ----------
        *args, **kwargs
            Forwarded to the parent widget constructor.
        """
        super().__init__(parent)
        self.mapCanvas = mapCanvas
        self.logger = logger
        self.data_manager = data_manager
        self.model_manager = model_manager

        mainLayout = QVBoxLayout(self)
        self.setLayout(mainLayout)
        tabWidget = QTabWidget(self)
        tabWidget.setTabPosition(QTabWidget.South)
        mainLayout.addWidget(tabWidget)
        self.modelling_widget = ModellingWidget(
            self,
            mapCanvas=self.mapCanvas,
            logger=self.logger,
            data_manager=self.data_manager,
            model_manager=self.model_manager,
        )

        self.visualisation_widget = VisualisationWidget(
            self, mapCanvas=self.mapCanvas, logger=self.logger, model_manager=self.model_manager
        )
        tabWidget.addTab(self.modelling_widget, "Modelling")
        tabWidget.addTab(self.visualisation_widget, "Visualisation")

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
