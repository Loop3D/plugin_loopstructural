import os

from PyQt5.QtWidgets import QWidget
from qgis.PyQt import uic

from loopstructural.gui.modelling.base_tab import BaseTab


class ModelDefinitionTab(BaseTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Load the UI file for Tab 1
        uic.loadUi(os.path.join(os.path.dirname(__file__), "model_definition_tab.ui"), self)
