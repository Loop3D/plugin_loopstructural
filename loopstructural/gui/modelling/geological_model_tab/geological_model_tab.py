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

from .feature_details_panel import (
    FaultFeatureDetailsPanel,
    FoldedFeatureDetailsPanel,
    FoliationFeatureDetailsPanel,
    StructuralFrameFeatureDetailsPanel,
)
from LoopStructural.modelling.features import FeatureType

# Import the AddFaultDialog
from .add_fault_dialog import AddFaultDialog
from .add_foliation_dialog import AddFoliationDialog


class GeologicalModelTab(QWidget):
    def __init__(self, parent=None, *, model_manager=None, data_manager=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self.data_manager = data_manager
        self.model_manager.observers.append(self.update_feature_list)
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
        add_foliaton = menu.addAction("Add Foliation")
        buttonPosition = self.sender().mapToGlobal(self.sender().rect().bottomLeft())
        action = menu.exec_(buttonPosition)

        if action == add_fault:
            self.open_add_fault_dialog()
        elif action == add_foliaton:
            self.open_add_foliation_dialog()

    def open_add_fault_dialog(self):
        dialog = AddFaultDialog(self)
        if dialog.exec_() == dialog.Accepted:
            fault_data = dialog.get_fault_data()
            # TODO: Add logic to use fault_data to add the fault to the model
            print("Fault data:", fault_data)

    def open_add_foliation_dialog(self):
        dialog = AddFoliationDialog(
            self, data_manager=self.data_manager, model_manager=self.model_manager
        )
        if dialog.exec_() == dialog.Accepted:
            pass

    def initialize_model(self):
        self.model_manager.update_model()

    def update_feature_list(self):
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
        feature_name = item.text(0)
        feature = self.model_manager.model.get_feature_by_name(feature_name)
        if feature.type == FeatureType.FAULT:
            self.featureDetailsPanel = FaultFeatureDetailsPanel(
                fault=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.INTERPOLATED:
            self.featureDetailsPanel = FoliationFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.STRUCTURALFRAME:
            self.featureDetailsPanel = StructuralFrameFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        elif feature.type == FeatureType.FOLDED:
            self.featureDetailsPanel = FoldedFeatureDetailsPanel(
                feature=feature, model_manager=self.model_manager, data_manager=self.data_manager
            )
        else:
            self.featureDetailsPanel = QWidget()  # Default empty panel

        # Dynamically replace the featureDetailsPanel widget
        splitter = self.layout().itemAt(1).widget()
        splitter.widget(1).deleteLater()  # Remove the existing widget
        splitter.addWidget(self.featureDetailsPanel)  # Add the new widget
