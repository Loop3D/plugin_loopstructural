from PyQt5.QtWidgets import (
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.feature_details_panel import FeatureDetailsPanel


class GeologicalModelTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        mainLayout = QVBoxLayout(self)

        # Splitter for collapsible layout
        splitter = QSplitter(self)
        mainLayout.addWidget(splitter)

        # Feature list panel
        self.featureList = QTreeWidget()
        self.featureList.setHeaderLabel("Geological Features")
        splitter.addWidget(self.featureList)

        # Feature details panel
        self.featureDetailsPanel = FeatureDetailsPanel()
        splitter.addWidget(self.featureDetailsPanel)

        # Action buttons
        self.saveButton = QPushButton("Save Changes")
        self.resetButton = QPushButton("Reset Parameters")
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.resetButton)

        # Connect signals
        self.saveButton.clicked.connect(self.save_changes)
        self.resetButton.clicked.connect(self.reset_parameters)

    def save_changes(self):
        # Logic to save changes
        pass

    def reset_parameters(self):
        # Logic to reset parameters
        pass
