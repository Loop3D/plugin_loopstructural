"""Dialog wrappers for map2loop processing tools.

This module provides QDialog wrappers that use map2loop classes directly
instead of QGIS processing algorithms.
"""

from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout


class SamplerDialog(QDialog):
    """Dialog for running samplers using map2loop classes directly."""

    def __init__(self, parent=None):
        """Initialize the sampler dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Sampler")
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .sampler_widget import SamplerWidget

        layout = QVBoxLayout(self)
        self.widget = SamplerWidget(self)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sampler and accept dialog if successful."""
        self.widget._run_sampler()
        # Dialog stays open so user can see the result


class SorterDialog(QDialog):
    """Dialog for running stratigraphic sorter using map2loop classes directly."""

    def __init__(self, parent=None):
        """Initialize the sorter dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Automatic Stratigraphic Sorter")
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .sorter_widget import SorterWidget

        layout = QVBoxLayout(self)
        self.widget = SorterWidget(self)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sorter and accept dialog if successful."""
        self.widget._run_sorter()


class UserDefinedSorterDialog(QDialog):
    """Dialog for user-defined stratigraphic column using map2loop classes directly."""

    def __init__(self, parent=None):
        """Initialize the user-defined sorter dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop User-Defined Stratigraphic Column")
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .user_defined_sorter_widget import UserDefinedSorterWidget

        layout = QVBoxLayout(self)
        self.widget = UserDefinedSorterWidget(self)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sorter and accept dialog if successful."""
        self.widget._run_sorter()


class BasalContactsDialog(QDialog):
    """Dialog for extracting basal contacts using map2loop classes directly."""

    def __init__(self, parent=None):
        """Initialize the basal contacts dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Basal Contacts Extractor")
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .basal_contacts_widget import BasalContactsWidget

        layout = QVBoxLayout(self)
        self.widget = BasalContactsWidget(self)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the extractor and accept dialog if successful."""
        self.widget._run_extractor()


class ThicknessCalculatorDialog(QDialog):
    """Dialog for calculating thickness using map2loop classes directly."""

    def __init__(self, parent=None):
        """Initialize the thickness calculator dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Thickness Calculator")
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .thickness_calculator_widget import ThicknessCalculatorWidget

        layout = QVBoxLayout(self)
        self.widget = ThicknessCalculatorWidget(self)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()
        
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the calculator and accept dialog if successful."""
        self.widget._run_calculator()
