from PyQt5.QtWidgets import QFormLayout, QLineEdit, QWidget


class FeatureDetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Layout for feature details
        self.featureDetailsLayout = QFormLayout(self)

        # Example fields for parameters and settings
        self.parameterInput = QLineEdit()
        self.settingInput = QLineEdit()
        self.featureDetailsLayout.addRow("Parameter:", self.parameterInput)
        self.featureDetailsLayout.addRow("Setting:", self.settingInput)

    def update_feature_details(self, feature):
        """Update the panel based on the selected feature."""
        # Logic to update fields based on the feature
        pass
