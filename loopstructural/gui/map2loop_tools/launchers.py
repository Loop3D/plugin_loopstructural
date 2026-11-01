"""Open the tool dialogs from the dock steps and from the plugin menu."""

SAMPLER = 'sampler'
SORTER = 'sorter'
USER_SORTER = 'user_sorter'
BASAL_CONTACTS = 'basal_contacts'
THICKNESS = 'thickness'
PAINT_STRAT_ORDER = 'paint_strat_order'
FAULT_TOPOLOGY = 'fault_topology'
DATA_CONVERSION = 'data_conversion'


def _dialog_class(tool):
    """Import the dialog class of a tool when it is needed (the imports are slow)."""
    if tool == DATA_CONVERSION:
        from loopstructural.gui.data_conversion import AutomaticConversionDialog

        return AutomaticConversionDialog
    if tool == FAULT_TOPOLOGY:
        from loopstructural.gui.map2loop_tools.fault_topology_widget import FaultTopologyWidget

        return FaultTopologyWidget
    from loopstructural.gui import map2loop_tools

    names = {
        SAMPLER: 'SamplerDialog',
        SORTER: 'SorterDialog',
        USER_SORTER: 'UserDefinedSorterDialog',
        BASAL_CONTACTS: 'BasalContactsDialog',
        THICKNESS: 'ThicknessCalculatorDialog',
        PAINT_STRAT_ORDER: 'PaintStratigraphicOrderDialog',
    }
    return getattr(map2loop_tools, names[tool])


def show_tool_dialog(tool, parent, *, data_manager, debug_manager=None):
    """Open the dialog of a tool and wait until the user closes it.

    Parameters
    ----------
    tool : str
        One of the names in this module, for example `BASAL_CONTACTS`.
    parent : QWidget
        Parent of the dialog.
    data_manager : ModellingDataManager
        The dialogs read the shared layers from the data manager.
    debug_manager : DebugManager, optional
        If this is None, the debug manager of the data manager is used.
    """
    dialog_class = _dialog_class(tool)
    if tool == DATA_CONVERSION:
        dialog = dialog_class(parent, project=data_manager.project if data_manager else None)
    else:
        if debug_manager is None and data_manager is not None:
            debug_manager = data_manager.debug_manager
        dialog = dialog_class(parent, data_manager=data_manager, debug_manager=debug_manager)
    dialog.exec()
