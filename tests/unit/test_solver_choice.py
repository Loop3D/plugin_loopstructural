"""Pytest tests for the choice of the solver (main/solver_choice.py).

The module does not import QGIS, so the tests run in the fast tests/unit/ job.
"""

from types import SimpleNamespace

from loopstructural.main import solver_choice


def _builder(solver=None):
    return SimpleNamespace(build_arguments={'solver': solver} if solver else {})


def test_native_is_used_only_if_it_is_installed(monkeypatch):
    monkeypatch.setattr(solver_choice, 'native_available', lambda: True)
    assert solver_choice.use_native(solver_choice.NATIVE)
    assert not solver_choice.use_native(solver_choice.DEFAULT)
    monkeypatch.setattr(solver_choice, 'native_available', lambda: False)
    assert not solver_choice.use_native(solver_choice.NATIVE)


def test_native_available_is_a_bool():
    assert isinstance(solver_choice.native_available(), bool)


def test_fallback_solver():
    assert solver_choice.fallback_solver(needs_inequalities=True) == 'admm'
    assert solver_choice.fallback_solver(needs_inequalities=False) == 'cg'


def test_builders_of_a_feature_and_of_a_frame():
    one = _builder()
    assert solver_choice.builders(SimpleNamespace(builder=one)) == [one]
    parts = [_builder(), _builder(), _builder()]
    frame = SimpleNamespace(builder=SimpleNamespace(builders=parts))
    assert solver_choice.builders(frame) == parts
    assert solver_choice.builders(SimpleNamespace()) == []


def test_uses_native():
    assert solver_choice.uses_native(SimpleNamespace(builder=_builder('native')))
    assert not solver_choice.uses_native(SimpleNamespace(builder=_builder('cg')))
    frame = SimpleNamespace(
        builder=SimpleNamespace(builders=[_builder('cg'), _builder('native'), _builder('cg')])
    )
    assert solver_choice.uses_native(frame)


def test_every_choice_has_a_label():
    assert set(solver_choice.LABELS) == set(solver_choice.CHOICES)
