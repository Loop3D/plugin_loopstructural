from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMenu,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Import the AddFaultDialog
from loopstructural.gui.modelling.add_fault_dialog import AddFaultDialog
from loopstructural.gui.modelling.add_fold_frame_dialog import AddFoldFrameDialog
from loopstructural.gui.modelling.feature_details_panel import (
    FaultFeatureDetailsPanel,
    FoliationFeatureDetailsPanel,
)
from LoopStructural.modelling.features import FeatureType


class GeologicalModelTab(QWidget):
    def __init__(self, parent=None, *, model_manager=None):
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
        side_panel = QVBoxLayout()
        side_panel.addWidget(self.featureList)
        add_feature_button = QPushButton("Add Feature")

        add_feature_button.setContextMenuPolicy(Qt.CustomContextMenu)
        add_feature_button.customContextMenuRequested.connect(self.show_add_feature_menu)
        add_feature_button.clicked.connect(self.show_add_feature_menu)
        side_panel.addWidget(add_feature_button)
        side_panel_widget = QWidget()
        side_panel_widget.setLayout(side_panel)
        splitter.addWidget(side_panel_widget)
        # self.splitter.addWidget(QWidget())  # Placeholder for the feature list panel
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

        self.initializeModelButton.clicked.connect(self.initialize_model)

        # Connect feature selection to update details panel
        self.featureList.itemClicked.connect(self.on_feature_selected)

    def show_add_feature_menu(self, *args):
        menu = QMenu(self)
        add_fault = menu.addAction("Add Fault")
        add_fold_frame = menu.addAction("Add Fold Frame")
        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec_(buttonPosition)

        if action == add_fault:
            self.open_add_fault_dialog()
        elif action == add_fold_frame:
            self.open_add_fold_frame_dialog()

    def open_add_fault_dialog(self):
        dialog = AddFaultDialog(self)
        if dialog.exec_() == dialog.Accepted:
            fault_data = dialog.get_fault_data()
            # TODO: Add logic to use fault_data to add the fault to the model
            print("Fault data:", fault_data)

    def open_add_fold_frame_dialog(self):
        dialog = AddFoldFrameDialog(self)
        if dialog.exec_() == dialog.Accepted:
            fold_data = dialog.get_fold_data()
            # TODO: Add logic to use fold_data to add the fold to the model
            print("Fold data:", fold_data)

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
            self.featureDetailsPanel = FoliationFeatureDetailsPanel(feature=feature)
        else:
            self.featureDetailsPanel = QWidget()  # Default empty panel

        # Dynamically replace the featureDetailsPanel widget
        splitter = self.layout().itemAt(1).widget()
        splitter.widget(1).deleteLater()  # Remove the existing widget
        splitter.addWidget(self.featureDetailsPanel)  # Add the new widget
