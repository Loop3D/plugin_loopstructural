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
# The iteration limit of a native solve, for each node of the grid (as cg)
NATIVE_ITERATIONS_PER_NODE = 10


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


def unsupported_builders(builders):
    """Return the indexes of the builders that use the native solver but that
    its core cannot solve, for example the coordinates 1 and 2 of a fault
    frame, which have orthogonal rows that the core cannot read.

    It uses the support check of loop-interpolation. Returns an empty list if
    the check is not available or finds no problem.
    """
    try:
        from loop_interpolation._native import check_supported
    except ImportError:
        return []
    failed = []
    for index, builder in enumerate(builders):
        if (getattr(builder, 'build_arguments', None) or {}).get('solver') != NATIVE:
            continue
        interpolator = getattr(builder, 'interpolator', None)
        if interpolator is None:
            continue
        try:
            check_supported(interpolator, getattr(interpolator, '_setup_kwargs', {}), {})
        except NotImplementedError:
            failed.append(index)
        except Exception:
            # the check is for one solve; any other problem is not a reason to change
            continue
    return failed


def native_solver_kwargs(builder):
    """Return the solver_kwargs for a native solve of `builder`, or None.

    The core stops after 5 000 iterations by default. The cg solver of scipy
    allows 10 x the number of nodes. With the default, a large grid can stop
    before it converges, so give the native solver the same limit as cg.
    """
    support = getattr(getattr(builder, 'interpolator', None), 'support', None)
    n_nodes = getattr(support, 'n_nodes', None)
    if not n_nodes:
        return None
    return {'maxiter': int(NATIVE_ITERATIONS_PER_NODE * n_nodes)}


def unconverged_builders(builders):
    """Return the indexes of the builders whose native solve did not converge.

    Then loop-interpolation keeps the old field of the interpolator, which can
    have the size of an old grid.
    """
    return [
        index
        for index, builder in enumerate(builders)
        if (getattr(builder, 'build_arguments', None) or {}).get('solver') == NATIVE
        and getattr(builder, 'interpolator', None) is not None
        and not getattr(builder.interpolator, 'up_to_date', True)
    ]


def uses_native(feature) -> bool:
    """Return True if a builder of the feature uses the native solver."""
    return any(
        (getattr(b, 'build_arguments', None) or {}).get('solver') == NATIVE
        for b in builders(feature)
    )
