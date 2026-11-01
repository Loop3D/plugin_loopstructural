"""Pytest tests for the one-task-at-a-time rule of the viewer widgets."""

from unittest.mock import patch

from loopstructural.gui.visualisation import model_task


class _Manager:
    pass


def test_a_second_task_waits_for_the_first():
    manager = _Manager()
    with patch.object(model_task, 'push_info') as info:
        assert model_task.try_start(manager, 'Isosurfaces')
        assert not model_task.try_start(manager, 'Block model')
        info.assert_called_once()
        assert 'Isosurfaces' in info.call_args[0][1]
        model_task.finish(manager)
        assert model_task.try_start(manager, 'Block model')


def test_no_manager_does_not_block():
    assert model_task.try_start(None, 'Isosurfaces')
    model_task.finish(None)
