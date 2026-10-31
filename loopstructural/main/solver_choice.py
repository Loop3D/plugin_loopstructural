"""Choose the solver of the interpolators: the native (Rust) solver or the default.

The native solver is ``solver='native'`` of loop-interpolation 0.2 and later.
It needs the package loop-interpolation-core (``pip install
loopstructural[native]``). It does not support all settings, for example a
fold interpolator or a region mask. For these, the model manager builds the
feature again with the default solver (see `fallback_solver`).

The module does not import QGIS, so the tests run in the fast tests/unit/ job.
"""

from importlib.util import find_spec

DEFAULT = 'default'
NATIVE = 'native'
CHOICES = (DEFAULT, NATIVE)
LABELS = {
    DEFAULT: "Default (Python)",
    NATIVE: "Native (fast, if it is installed)",
}

# The errors that tell that the native solver cannot solve a feature
NATIVE_ERRORS = (NotImplementedError, ImportError)


def native_available() -> bool:
    """Return True if loop-interpolation has the native solver and its core is installed."""
    try:
        return (
            find_spec('loop_interpolation_core') is not None
            and find_spec('loop_interpolation._native') is not None
        )
    except (ImportError, ValueError):
        return False


def use_native(setting: str) -> bool:
    """Return True if the setting asks for the native solver and it is installed."""
    return setting == NATIVE and native_available()


def fallback_solver(needs_inequalities: bool):
    """Return the solver for a feature that the native solver cannot solve.

    Inequality constraints need ADMM. Otherwise the default of LoopStructural (cg).
    """
    return 'admm' if needs_inequalities else 'cg'


def builders(feature):
    """Return the builders of a feature: one, or the three of a structural frame."""
    builder = getattr(feature, 'builder', None)
    if builder is None:
        return []
    return list(getattr(builder, 'builders', None) or [builder])


def uses_native(feature) -> bool:
    """Return True if a builder of the feature uses the native solver."""
    return any(
        (getattr(b, 'build_arguments', None) or {}).get('solver') == NATIVE
        for b in builders(feature)
    )
