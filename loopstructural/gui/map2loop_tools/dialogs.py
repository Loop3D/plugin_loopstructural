"""Dialog wrappers for map2loop processing tools.

This module provides QDialog wrappers that use map2loop classes directly
instead of QGIS processing algorithms.
"""

from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout


class _EmbeddedWidgetDialog(QDialog):
    """Base for a QDialog that just embeds one of the map2loop tool widgets.

    The six dialogs below previously copy-pasted the same layout/OK-Cancel
    wiring, differing only in window title, which widget they embed, and
    which method on that widget actually runs the tool. Subclasses set
    `window_title`/`run_method_name` and implement `_make_widget`.
    """

    window_title: str = ""
    run_method_name: str = ""

    def _make_widget(self, parent, data_manager, debug_manager):
        """Construct and return the embedded tool widget."""
        raise NotImplementedError

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.setWindowTitle(self.window_title)
        self.data_manager = data_manager
        self.debug_manager = debug_manager
        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        self.widget = self._make_widget(self, self.data_manager, self.debug_manager)
        layout.addWidget(self.widget)

        # Replace the widget's own run button (if it has one) with dialog buttons
        run_button = getattr(self.widget, 'runButton', None)
        if run_button is not None:
            run_button.hide()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.button_box.accepted.connect(self._run_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Widgets whose run method starts a background task (see
        # loopstructural.gui.background_task) can't return a synchronous
        # True/False, so they signal completion instead -- see
        # _run_and_accept. Widgets that still run synchronously don't
        # define these, so this is a no-op for them.
        task_succeeded = getattr(self.widget, 'task_succeeded', None)
        if task_succeeded is not None:
            task_succeeded.connect(self.accept)
        task_failed = getattr(self.widget, 'task_failed', None)
        if task_failed is not None:
            task_failed.connect(self._on_widget_task_failed)

    def _run_and_accept(self):
        """Run the tool and accept the dialog if it succeeded.

        A widget still running its tool synchronously returns True/False
        directly, exactly as before. A widget that's been moved onto a
        background QThread instead returns None once validation passes and
        the task has been started -- the dialog stays open (with its
        buttons disabled so the user can't close it out from under a
        still-running worker thread) until the widget's `task_succeeded`/
        `task_failed` signal fires (connected in `setup_ui`).
        """
        result = getattr(self.widget, self.run_method_name)()
        if result is True:
            self.accept()
        elif result is None and hasattr(self.widget, 'task_succeeded'):
            self.button_box.setEnabled(False)

    def _on_widget_task_failed(self):
        self.button_box.setEnabled(True)


class SamplerDialog(_EmbeddedWidgetDialog):
    """Dialog for running samplers using map2loop classes directly."""

    window_title = "Map2Loop Sampler"
    run_method_name = "_run_sampler"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .sampler_widget import SamplerWidget

        return SamplerWidget(parent, data_manager=data_manager, debug_manager=debug_manager)


class SorterDialog(_EmbeddedWidgetDialog):
    """Dialog for running stratigraphic sorter using map2loop classes directly."""

    window_title = "Map2Loop Automatic Stratigraphic Sorter"
    run_method_name = "_run_sorter"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .sorter_widget import SorterWidget

        return SorterWidget(parent, data_manager=data_manager, debug_manager=debug_manager)


class UserDefinedSorterDialog(_EmbeddedWidgetDialog):
    """Dialog for user-defined stratigraphic column using map2loop classes directly."""

    window_title = "Map2Loop User-Defined Stratigraphic Column"
    run_method_name = "_run_sorter"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .user_defined_sorter_widget import UserDefinedSorterWidget

        return UserDefinedSorterWidget(
            parent, data_manager=data_manager, debug_manager=debug_manager
        )


class BasalContactsDialog(_EmbeddedWidgetDialog):
    """Dialog for extracting basal contacts using map2loop classes directly."""

    window_title = "Map2Loop Basal Contacts Extractor"
    run_method_name = "_run_extractor"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .basal_contacts_widget import BasalContactsWidget

        return BasalContactsWidget(parent, data_manager=data_manager, debug_manager=debug_manager)


class ThicknessCalculatorDialog(_EmbeddedWidgetDialog):
    """Dialog for calculating thickness using map2loop classes directly."""

    window_title = "Map2Loop Thickness Calculator"
    run_method_name = "_run_calculator"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .thickness_calculator_widget import ThicknessCalculatorWidget

        return ThicknessCalculatorWidget(
            parent, data_manager=data_manager, debug_manager=debug_manager
        )


class PaintStratigraphicOrderDialog(_EmbeddedWidgetDialog):
    """Dialog for painting stratigraphic order onto geology polygons."""

    window_title = "Paint Stratigraphic Order"
    run_method_name = "_run_painter"

    def _make_widget(self, parent, data_manager, debug_manager):
        from .paint_stratigraphic_order_widget import PaintStratigraphicOrderWidget

        return PaintStratigraphicOrderWidget(
            parent, data_manager=data_manager, debug_manager=debug_manager
        )
