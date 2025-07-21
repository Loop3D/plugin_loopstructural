from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from loopstructural.gui.modelling.feature_details_panel import FaultFeatureDetailsPanel, FoliationFeatureDetailsPanel

from LoopStructural.modelling.features import FeatureType

class GeologicalModelTab(QWidget):
    def __init__(self, parent=None,*, model_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager

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
        self.featureDetailsPanel = QWidget()
        splitter.addWidget(self.featureDetailsPanel)

        # Limit feature details panel expansion
        splitter.setStretchFactor(0, 1)  # Feature list panel
        splitter.setStretchFactor(1, 0)  # Feature details panel
        splitter.setOrientation(Qt.Horizontal)  # Add horizontal slider

        # Initialize Model button
        self.initializeModelButton = QPushButton("Initialize Model")
        mainLayout.insertWidget(0, self.initializeModelButton)

        # Action buttons
        self.saveButton = QPushButton("Save Changes")
        self.resetButton = QPushButton("Reset Parameters")
        mainLayout.addWidget(self.saveButton)
        mainLayout.addWidget(self.resetButton)

        # Connect signals
        self.saveButton.clicked.connect(self.save_changes)
        self.resetButton.clicked.connect(self.reset_parameters)
        self.initializeModelButton.clicked.connect(self.initialize_model)

        # Connect feature selection to update details panel
        self.featureList.itemClicked.connect(self.on_feature_selected)

    def save_changes(self):
        # Logic to save changes
        pass

    def reset_parameters(self):
        # Logic to reset parameters
        pass

    def initialize_model(self):
        self.model_manager.update_model()
        self.featureList.clear()  # Clear the feature list before populating it
        for feature in self.model_manager.features():
            if feature.name.startswith("__"):
                continue
            items = self.featureList.findItems(feature.name, Qt.MatchExactly)
            if items:
                # If the feature already exists, skip adding it again
                continue
            item = QTreeWidgetItem(self.featureList)
            item.setText(0, feature.name)
            item.setData(0, 1, feature)
            self.featureList.addTopLevelItem(item)
        # self.featureList.itemClicked.connect(self.on_feature_selected)

    def on_feature_selected(self, item):
        feature = item.data(0, 1)
        if feature.type == FeatureType.FAULT:
            print("Fault feature selected")
            self.featureDetailsPanel = FaultFeatureDetailsPanel(fault=feature)
        elif feature.type == FeatureType.INTERPOLATED:
            self.featureDetailsPanel = FoliationFeatureDetailsPanel(feature=feature )
        else:
            self.featureDetailsPanel = QWidget()  # Default empty panel

        # Dynamically replace the featureDetailsPanel widget
        splitter = self.layout().itemAt(1).widget()
        splitter.widget(1).deleteLater()  # Remove the existing widget
        splitter.addWidget(self.featureDetailsPanel)  # Add the new widget
