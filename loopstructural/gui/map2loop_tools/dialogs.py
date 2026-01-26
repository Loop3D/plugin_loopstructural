"""Dialog wrappers for map2loop processing tools.

This module provides QDialog wrappers that use map2loop classes directly
instead of QGIS processing algorithms.
"""

from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout


class SamplerDialog(QDialog):
    """Dialog for running samplers using map2loop classes directly."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the sampler dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Sampler")
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .sampler_widget import SamplerWidget

        layout = QVBoxLayout(self)
        self.widget = SamplerWidget(self, data_manager=self.data_manager, debug_manager=self.debug_manager)
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sampler and accept dialog if successful."""
        if self.widget._run_sampler():
            self.accept()


class SorterDialog(QDialog):
    """Dialog for running stratigraphic sorter using map2loop classes directly."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the sorter dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Automatic Stratigraphic Sorter")
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .sorter_widget import SorterWidget

        layout = QVBoxLayout(self)
        self.widget = SorterWidget(
            self,
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sorter and accept dialog if successful."""
        if self.widget._run_sorter():
            self.accept()


class UserDefinedSorterDialog(QDialog):
    """Dialog for user-defined stratigraphic column using map2loop classes directly."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the user-defined sorter dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop User-Defined Stratigraphic Column")
        self.data_manager = data_manager
        self.debug_manager = debug_manager

        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .user_defined_sorter_widget import UserDefinedSorterWidget

        layout = QVBoxLayout(self)
        self.widget = UserDefinedSorterWidget(
            self,
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the sorter and accept dialog if successful."""
        if self.widget._run_sorter():
            self.accept()


class BasalContactsDialog(QDialog):
    """Dialog for extracting basal contacts using map2loop classes directly."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the basal contacts dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Basal Contacts Extractor")
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .basal_contacts_widget import BasalContactsWidget

        layout = QVBoxLayout(self)
        self.widget = BasalContactsWidget(
            self,
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the extractor and accept dialog if successful."""
        if self.widget._run_extractor():
            self.accept()


class ThicknessCalculatorDialog(QDialog):
    """Dialog for calculating thickness using map2loop classes directly."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the thickness calculator dialog."""
        super().__init__(parent)
        self.setWindowTitle("Map2Loop Thickness Calculator")
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .thickness_calculator_widget import ThicknessCalculatorWidget

        layout = QVBoxLayout(self)
        self.widget = ThicknessCalculatorWidget(
            self,
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the calculator and accept dialog if successful."""
        if self.widget._run_calculator():
            self.accept()


class PaintStratigraphicOrderDialog(QDialog):
    """Dialog for painting stratigraphic order onto geology polygons."""

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the paint stratigraphic order dialog."""
        super().__init__(parent)
        self.setWindowTitle("Paint Stratigraphic Order")
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        from .paint_stratigraphic_order_widget import PaintStratigraphicOrderWidget

        layout = QVBoxLayout(self)
        self.widget = PaintStratigraphicOrderWidget(
            self,
            data_manager=self.data_manager,
            debug_manager=self.debug_manager,
        )
        layout.addWidget(self.widget)

        # Replace the run button with dialog buttons
        self.widget.runButton.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _run_and_accept(self):
        """Run the painter and accept dialog if successful."""
        if self.widget._run_painter():
            self.accept()
