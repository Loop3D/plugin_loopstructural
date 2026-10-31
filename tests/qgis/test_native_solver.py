"""Pytest tests for the native solver in the model manager.

The features are small stand-ins: the tests check the choice of the solver and
the fallback, not LoopStructural.
"""

import pytest

from loopstructural.main import model_manager as model_manager_module
from loopstructural.main import solver_choice
from loopstructural.main.model_manager import GeologicalModelManager
from loopstructural.toolbelt.preferences import PlgSettingsStructure


class _DebugManager:
    def __init__(self):
        self.messages = []

    def log(self, message, *args, **kwargs):
        self.messages.append(message)


class _Builder:
    def __init__(self, solver):
        self.build_arguments = {'solver': solver}
        self.solvers = []

    def update_build_arguments(self, arguments):
        self.build_arguments.update(arguments)

    def update(self):
        solver = self.build_arguments.get('solver')
        self.solvers.append(solver)
        if solver == solver_choice.NATIVE:
            raise NotImplementedError("solver='native' does not support the setting 'region'")

    up_to_date = update


class _Feature:
    def __init__(self, name, solver=solver_choice.NATIVE):
        self.name = name
        self.builder = _Builder(solver)


def _use(monkeypatch, solver, available=True):
    settings = PlgSettingsStructure(interpolator_solver=solver)
    monkeypatch.setattr(
        model_manager_module.PlgOptionsManager, 'get_plg_settings', staticmethod(lambda: settings)
    )
    monkeypatch.setattr(solver_choice, 'native_available', lambda: available)


@pytest.fixture
def manager():
    return GeologicalModelManager(debug_manager=_DebugManager())


def test_native_is_passed_when_it_is_chosen_and_installed(manager, monkeypatch):
    _use(monkeypatch, solver_choice.NATIVE)
    assert manager.interpolator_arguments('s1', None)['solver'] == 'native'


def test_no_solver_is_passed_without_native(manager, monkeypatch):
    _use(monkeypatch, solver_choice.DEFAULT)
    assert 'solver' not in manager.interpolator_arguments('s1', None)
    _use(monkeypatch, solver_choice.NATIVE, available=False)
    assert 'solver' not in manager.interpolator_arguments('s1', None)


def test_native_also_solves_the_inequalities(manager, monkeypatch):
    _use(monkeypatch, solver_choice.NATIVE)
    assert manager._inequality_solver('s1', 'admm') is None
    _use(monkeypatch, solver_choice.DEFAULT)
    assert manager._inequality_solver('s1', 'admm') == 'admm'
    assert manager._inequality_solver('s1', None) is None


def test_a_feature_that_native_cannot_solve_uses_the_default(manager, monkeypatch):
    _use(monkeypatch, solver_choice.NATIVE)
    feature = _Feature('s1')
    manager._solve_feature(feature)
    assert feature.builder.solvers == ['native', 'cg']
    assert 's1' in manager._native_failed
    assert any('native' in message for message in manager._debug_manager.messages)
    # the next build of the feature does not try native again
    assert 'solver' not in manager.interpolator_arguments('s1', None)


def test_the_fallback_of_inequalities_is_admm(manager, monkeypatch):
    _use(monkeypatch, solver_choice.NATIVE)
    manager._inequality_solver('s1', 'admm')
    feature = _Feature('s1')
    manager._solve_feature(feature, rebuild=False)
    assert feature.builder.solvers == ['native', 'admm']


def test_an_error_without_native_is_raised(manager, monkeypatch):
    _use(monkeypatch, solver_choice.DEFAULT)

    class _Failing(_Builder):
        def update(self):
            raise NotImplementedError("something else")

    feature = _Feature('s1', solver='cg')
    feature.builder = _Failing('cg')
    with pytest.raises(NotImplementedError):
        manager._solve_feature(feature)
