import os
import pickle
import importlib
import pytest

from qgis.core import QgsApplication, QgsProcessingContext, QgsProcessingFeedback


@pytest.fixture(scope="session", autouse=True)
def qgis_app():
    """Start a headless QGIS application for tests.

    Requires QGIS_PREFIX_PATH to be set in the environment (pointing to the QGIS install).
    """
    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if not prefix:
        raise RuntimeError(
            "QGIS_PREFIX_PATH environment variable must be set to your QGIS install path for tests to run."
        )

    app = QgsApplication([], False)
    app.setPrefixPath(prefix, True)
    app.initQgis()

    yield app

    app.exitQgis()


@pytest.fixture
def qgis_context():
    """Return a fresh processing context."""
    return QgsProcessingContext()


@pytest.fixture
def feedback():
    """Return a simple QgsProcessingFeedback instance for algorithms."""
    return QgsProcessingFeedback()


@pytest.fixture
def ensure_loopstructural(monkeypatch):
    """If the real LoopStructural classes are not available, inject minimal fakes into
    the algorithm module so tests can run without the external dependency.

    The algorithm module imports FaultTopology and FaultRelationshipType at import-time
    and uses those module-level names; this fixture patches the algorithm module
    attributes when they are missing.
    """
    mod_name = "loopstructural.processing.algorithms.modelling.add_fault_topology"
    mod = importlib.import_module(mod_name)

    if getattr(mod, "FaultTopology", None) is not None and getattr(mod, "FaultRelationshipType", None) is not None:
        # real dependency present; nothing to do
        return

    class _FakeFaultTopology:
        def __init__(self, strat_col=None):
            self.strat_col = strat_col
            self.faults = set()
            # store relationships in a dict for simple inspection
            self._rels = {}

        def add_fault(self, name):
            self.faults.add(name)

        def update_fault_relationship(self, a, b, rel):
            self._rels[(a, b)] = rel

        def __repr__(self):
            return f"FakeFaultTopology(faults={sorted(self.faults)})"

    class _FakeFaultRelationshipType:
        ABUTTING = 1

    monkeypatch.setattr(mod, "FaultTopology", _FakeFaultTopology, raising=False)
    monkeypatch.setattr(mod, "FaultRelationshipType", _FakeFaultRelationshipType, raising=False)

    return


@pytest.fixture
def simple_model_pickle(tmp_path):
    """Create and return a path to a simple pickled model object suitable for tests.

    The returned object has a `features` attribute with simple feature-like objects
    exposing a `name` attribute so the algorithm can find faults.
    """
    class DummyFeature:
        def __init__(self, name):
            self.name = name

        def __repr__(self):
            return f"DummyFeature({self.name})"

    class DummyModel:
        def __init__(self, names=("fault1", "fault2")):
            self.features = [DummyFeature(n) for n in names]

        def __repr__(self):
            return f"DummyModel(features={self.features})"

    model = DummyModel()
    path = tmp_path / "model.pkl"
    with open(path, "wb") as fh:
        pickle.dump(model, fh)

    return str(path)
