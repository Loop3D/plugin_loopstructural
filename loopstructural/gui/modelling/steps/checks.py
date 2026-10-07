"""Check functions of the steps of the modelling dock.

Each function reads the state of the data manager and the model manager and
returns a `StepCheck`. The functions are cheap, because the dock calls them
often. They do not change the state.
"""

from loopstructural.main import derived_data, layer_roles
from loopstructural.main.workflow_mode import WORKFLOW_MODE_CONSTRAINTS

from .status import StepCheck

STEP_DATA = 'data'
STEP_STRATIGRAPHY = 'stratigraphy'
STEP_FAULTS = 'faults'
STEP_MODEL = 'model'
STEP_VIEW = 'view'

# The words for the inputs that changed, in the message of an out-of-date result
_INPUT_WORDS = {
    'unit_order': 'the order of the units',
    'geology': 'the geology layer',
    'unit_field': 'the unit name field',
    'faults': 'the faults layer',
    'ignore_units': 'the ignored units',
    'override_units': 'the basal override units',
    'contacts': 'the basal contacts settings',
    'calculator_type': 'the calculator type',
    'structure': 'the structure layer',
    'cross_sections': 'the cross-sections layer',
    'thicknesses': 'a unit thickness',
}


def _out_of_date_messages(data_manager):
    """Return a message for each derived result that is out of date."""
    derived = data_manager.derived
    messages = []
    for name in (derived_data.BASAL_CONTACTS, derived_data.THICKNESS, derived_data.STYLED_FIELDS):
        if not derived.is_out_of_date(name):
            continue
        # With "Use a contacts layer", the contacts are an input of the user.
        if (
            name == derived_data.BASAL_CONTACTS
            and data_manager.layer_roles.contacts_source == layer_roles.CONTACTS_FROM_LAYER
        ):
            continue
        words = [
            _INPUT_WORDS.get(key, key.replace('_', ' ')) for key in derived.changed_inputs(name)
        ]
        reason = f" ({', '.join(words)} changed)" if words else ""
        messages.append(f"{derived_data.DESCRIPTIONS[name]} are out of date{reason}.")
    return messages


def check_data(data_manager, model_manager=None) -> StepCheck:
    """Step 1: the area, the coordinate system and the source layers."""
    problems, todo = [], []
    if not data_manager.is_bounding_box_set():
        todo.append("Set the bounding box.")
    if not data_manager.is_model_crs_valid():
        problems.append("The model CRS must be a projected CRS (in metres).")
    return StepCheck(tuple(problems), tuple(todo))


def check_stratigraphy(data_manager, model_manager=None) -> StepCheck:
    """Step 2: the column and the results that come from it."""
    problems, todo = [], []
    unit_names = data_manager.get_stratigraphic_unit_names()
    if not unit_names:
        # The step is optional: a model of faults only has no column
        todo.append(
            "Add units to the stratigraphic column. This step is optional if you model "
            "only faults."
        )
        return StepCheck(tuple(problems), tuple(todo))
    if data_manager.get_layer_role(layer_roles.GEOLOGY) is None:
        todo.append("Select the geology layer.")
    if data_manager.get_layer_role(layer_roles.STRUCTURE) is None:
        todo.append("Select the structure layer.")
    problems.extend(_out_of_date_messages(data_manager))

    contact_units = set(data_manager.get_unique_basal_units())
    if unit_names and contact_units:
        missing = [name for name in unit_names if name not in contact_units]
        if missing:
            count = len(missing)
            names = ', '.join(missing[:3]) + (', ...' if count > 3 else '')
            noun = 'unit has' if count == 1 else 'units have'
            problems.append(f"{count} {noun} no basal contacts: {names}.")
    if unit_names and data_manager.get_layer_role(layer_roles.BASAL_CONTACTS) is None:
        todo.append("Extract the basal contacts.")
    return StepCheck(tuple(problems), tuple(todo))


def check_faults(data_manager, model_manager=None) -> StepCheck:
    """Step 3: the faults. A model can have no faults, so this step is optional."""
    traces = data_manager.get_fault_traces()
    if not traces or traces.get('layer') is None:
        return StepCheck(todo=("No fault layer is selected. Faults are optional.",))
    if not traces.get('fault_name_field'):
        return StepCheck(todo=("Select the fault name field.",))
    if not data_manager._fault_topology.faults:
        return StepCheck(problems=("The fault layer has no faults.",))
    return StepCheck()


def check_model(data_manager, model_manager=None) -> StepCheck:
    """Step 4: the model."""
    problems, todo = [], []
    if not data_manager.is_bounding_box_set():
        problems.append("Set the bounding box in step 1.")
    if not data_manager.is_model_crs_valid():
        problems.append("The model CRS must be a projected CRS (in metres).")
    # With constraints only, there is no column, so no result comes from it
    if getattr(data_manager, 'workflow_mode', None) != WORKFLOW_MODE_CONSTRAINTS:
        problems.extend(_out_of_date_messages(data_manager))
    changed = data_manager.get_changed_layers()
    if changed:
        problems.append("Input layers changed after the model was built: " + ", ".join(changed))
    state = model_manager.model_state if model_manager is not None else 'empty'
    if state == 'empty':
        todo.append("Initialise the model.")
    elif state == 'stale':
        problems.append("Inputs changed after the model was built. Initialise the model again.")
    elif state == 'initialized':
        todo.append("Solve the model.")
    return StepCheck(tuple(problems), tuple(todo))


def check_view(data_manager, model_manager=None) -> StepCheck:
    """Step 5: the view. It needs a solved model."""
    state = model_manager.model_state if model_manager is not None else 'empty'
    if state != 'solved':
        return StepCheck(todo=("Solve the model in step 4 first.",))
    return StepCheck()


STEP_CHECKS = {
    STEP_DATA: check_data,
    STEP_STRATIGRAPHY: check_stratigraphy,
    STEP_FAULTS: check_faults,
    STEP_MODEL: check_model,
    STEP_VIEW: check_view,
}
