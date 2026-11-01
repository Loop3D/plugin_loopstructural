"""The start choice of the user: how the model is built.

This module does not import QGIS, so the unit tests can run it.
"""

# Steps 2 (stratigraphy) and 3 (faults) make features and constraints for step 4.
WORKFLOW_MODE_MAP = 'map'
# Steps 2 and 3 are hidden. The user gives the constraints in step 4.
WORKFLOW_MODE_CONSTRAINTS = 'constraints'
WORKFLOW_MODES = (WORKFLOW_MODE_MAP, WORKFLOW_MODE_CONSTRAINTS)
DEFAULT_WORKFLOW_MODE = WORKFLOW_MODE_MAP

WORKFLOW_MODE_LABELS = {
    WORKFLOW_MODE_MAP: "Build from a geological map",
    WORKFLOW_MODE_CONSTRAINTS: "Interpolate surfaces from constraints",
}

# The steps that the "constraints" choice hides. The user can show them later.
CONSTRAINT_MODE_HIDDEN_STEPS = ('stratigraphy', 'faults')
