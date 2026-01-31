"""Widget for user-defined stratigraphic column."""

from typing import Any

from PyQt5.QtWidgets import QVBoxLayout, QWidget

from loopstructural.gui.modelling.stratigraphic_column import StratColumnWidget


class UserDefinedSorterWidget(QWidget):
    """Widget for creating a user-defined stratigraphic column.

    This widget uses the LoopStructural StratigraphicColumn widget
    and links it to the data manager for integration with the model.
    """

    def __init__(self, parent=None, data_manager=None, debug_manager=None):
        """Initialize the user-defined sorter widget.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        """
        super().__init__(parent)

        if data_manager is None:
            raise ValueError("data_manager must be provided")

        self.data_manager = data_manager
        self._debug = debug_manager

        # Load the UI file

        # Create and add the StratigraphicColumn widget to the UI
        self.strat_column_widget = StratColumnWidget(parent=self, data_manager=self.data_manager)

        # Add the stratigraphic column widget to the UI layout
        # Assuming the UI has a placeholder widget or layout for this
        if hasattr(self, 'stratiColumnWidget'):
            # If the UI has a widget called stratiColumnWidget, use ruits layout
            layout = self.stratiColumnWidget.layout()
            if layout is None:
                layout = QVBoxLayout(self.stratiColumnWidget)
            layout.addWidget(self.strat_column_widget)
        else:
            # Otherwise, add it to the main layout
            main_layout = self.layout()
            if main_layout is None:
                main_layout = QVBoxLayout(self)
            main_layout.addWidget(self.strat_column_widget)

    def set_debug_manager(self, debug_manager):
        """Attach a debug manager instance."""
        self._debug = debug_manager

    def _log_params(self, context_label: str, params: Any):
        if getattr(self, "_debug", None):
            self._debug.log_params(context_label=context_label, params=params)

    def _run_sorter(self):
        """Run the user-defined stratigraphic sorter algorithm.

        This method will use the stratigraphic column from the StratColumnWidget
        that is already linked to the data manager, ensuring the model is updated.
        """
        # this sorter doesn't do anything and the updates are handled by the strat column widget
        return True

    def get_stratigraphic_column(self):
        """Get the current stratigraphic column from the data manager.

        Returns
        -------
        list
            List of unit names from youngest to oldest.
        """
        if hasattr(self, 'data_manager') and self.data_manager is not None:
            strati_column = self.data_manager.get_stratigraphic_column()
            # Extract unit names in order
            unit_names = []
            for element in strati_column.order:
                if hasattr(element, 'name'):
                    unit_names.append(element.name)
            return unit_names
        return []

    def set_stratigraphic_column(self, units):
        """Set the stratigraphic column in the data manager.

        Parameters
        ----------
        units : list
            List of unit names from youngest to oldest.
        """
        if not hasattr(self, 'data_manager') or self.data_manager is None:
            raise ValueError("data_manager is not initialized")

        # Clear the existing column
        self.data_manager._stratigraphic_column.clear()

        # Add each unit to the stratigraphic column
        for unit_name in units:
            self.data_manager.add_to_stratigraphic_column(
                {'type': 'unit', 'name': unit_name, 'colour': None}
            )

        # The callback is already called by add_to_stratigraphic_column
        # But we still update the display to be safe
        if hasattr(self, 'strat_column_widget'):
            self.strat_column_widget.update_display()
