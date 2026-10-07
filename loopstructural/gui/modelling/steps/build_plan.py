"""The primary action of the model step.

One button replaces "Initialize Model", "Solve Model" and "Update Model
Data". The text and the action of the button come from the state of the model
and from the derived data. This module does not import QGIS, so the unit tests
can run it.
"""

from dataclasses import dataclass

from loopstructural.main.workflow_mode import (
    CONSTRAINT_MODE_HIDDEN_STEPS,
    WORKFLOW_MODE_CONSTRAINTS,
)

# The actions of the primary button
ACTION_BUILD = 'build'  # make the features again, then solve them
ACTION_SOLVE = 'solve'  # solve the features that exist
ACTION_NONE = 'none'  # nothing can be done now

@dataclass(frozen=True)
class PrimaryAction:
    """The text, the action and the enabled state of the primary button."""

    action: str
    text: str
    enabled: bool = True
    tooltip: str = ""


def choose_primary_action(
    model_state,
    *,
    derived_out_of_date=(),
    layers_changed=False,
    blocked_reason=None,
) -> PrimaryAction:
    """Return the action of the primary button.

    Parameters
    ----------
    model_state : str
        `GeologicalModelManager.model_state`: empty, initialized, solved or stale.
    derived_out_of_date : iterable of str
        Names of the derived results that the build calculates again.
    layers_changed : bool
        True if an input layer changed after the model data was read.
    blocked_reason : str, optional
        A problem that stops every build, for example no bounding box.
    """
    if blocked_reason:
        return PrimaryAction(ACTION_NONE, "Build model", False, blocked_reason)
    derived_out_of_date = list(derived_out_of_date)
    if model_state == 'empty':
        return PrimaryAction(
            ACTION_BUILD, "Build model", tooltip="Make the features and solve them."
        )
    if model_state == 'stale' or derived_out_of_date:
        if derived_out_of_date:
            reason = "The data that comes from the column is out of date."
        else:
            reason = "The inputs changed after the model was built."
        return PrimaryAction(
            ACTION_BUILD,
            "Rebuild model",
            tooltip=f"{reason} Make the features again and solve them.",
        )
    if layers_changed:
        return PrimaryAction(
            ACTION_SOLVE,
            "Update data and solve",
            tooltip=(
                "An input layer changed. Read the layers again, put the new data into "
                "the features, and solve them."
            ),
        )
    if model_state == 'initialized':
        return PrimaryAction(ACTION_SOLVE, "Solve model", tooltip="Solve the features.")
    return PrimaryAction(
        ACTION_SOLVE, "Solve again", tooltip="Solve the features again with their current settings."
    )


def collect_problems(step_checks):
    """Return the problems of all steps as ``(step_key, message)`` pairs.

    Parameters
    ----------
    step_checks : iterable of (str, StepCheck)
        The step keys and the results of their checks, in the order of the steps.
    """
    problems = []
    seen = set()
    for key, check in step_checks:
        for message in check.problems:
            # The same problem can show in more than one step
            if message in seen:
                continue
            seen.add(message)
            problems.append((key, message))
    return problems


def steps_for_mode(mode, all_steps):
    """Return the step keys that the start choice shows.

    With "Interpolate surfaces from constraints", the stratigraphy and fault
    steps are hidden. The user can show them later.
    """
    hidden = CONSTRAINT_MODE_HIDDEN_STEPS if mode == WORKFLOW_MODE_CONSTRAINTS else ()
    return [key for key in all_steps if key not in hidden]
