"""Map2Loop tools tab for the modelling widget."""

from loopstructural.gui.modelling.base_tab import BaseTab

from ..map2loop_tools import (
    BasalContactsWidget,
    SamplerWidget,
    SorterWidget,
    ThicknessCalculatorWidget,
    UserDefinedSorterWidget,
)


class Map2LoopToolsTab(BaseTab):
    """Tab containing map2loop processing tools.

    This tab provides GUI interfaces for all map2loop processing tools,
    including stratigraphic sorters, samplers, basal contacts extraction,
    and thickness calculation.
    """

    def __init__(self, parent=None, data_manager=None):
        """Initialize the Map2Loop tools tab.

        Parameters
        ----------
        parent : QWidget, optional
            Parent widget.
        data_manager : object, optional
            Data manager for accessing shared data.
        """
        super().__init__(parent, data_manager, scrollable=True)

        # Create widgets for each map2loop tool
        self.sorter_widget = SorterWidget(self, data_manager)
        self.user_defined_sorter_widget = UserDefinedSorterWidget(self, data_manager)
        self.basal_contacts_widget = BasalContactsWidget(self, data_manager)
        self.sampler_widget = SamplerWidget(self, data_manager)
        self.thickness_calculator_widget = ThicknessCalculatorWidget(self, data_manager)

        # Add widgets to the tab with collapsible group boxes
        self.add_widget(self.sorter_widget, 'Automatic Stratigraphic Sorter')
        self.add_widget(self.user_defined_sorter_widget, 'User-Defined Stratigraphic Column')
        self.add_widget(self.basal_contacts_widget, 'Basal Contacts Extractor')
        self.add_widget(self.sampler_widget, 'Sampler')
        self.add_widget(self.thickness_calculator_widget, 'Thickness Calculator')
