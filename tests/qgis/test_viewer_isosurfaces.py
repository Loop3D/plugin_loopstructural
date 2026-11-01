"""Isosurfaces from a model feature: the objects get the right names and
isovalues, and a changed value changes only that object.

The viewer is a small stand-in (it keeps the objects in the registry, as the
real viewer does), so the tests do not need pyvistaqt.
"""

from unittest.mock import Mock, patch

import pytest

from loopstructural.gui.visualisation.feature_list_widget import FeatureListWidget
from loopstructural.gui.visualisation.object_registry import ObjectRegistry, ViewerObject


class FakeViewer:
    def __init__(self):
        self.registry = ObjectRegistry()
        self.outOfDateChanged = Mock()

    def add_mesh_object(self, mesh, name, **kwargs):
        self.registry.add(
            ViewerObject(
                name,
                mesh,
                source_feature=kwargs.get('source_feature'),
                source_type=kwargs.get('source_type'),
                isovalue=kwargs.get('isovalue'),
                out_of_date=kwargs.get('out_of_date', False),
            )
        )

    def replace_mesh_object(self, name, mesh=None, overrides=None, *, new_name=None, **updates):
        obj = self.registry.get(name)
        if new_name and new_name != name:
            self.registry.remove(name)
            obj.name = new_name
            self.registry.add(obj)
        obj.mesh = mesh
        obj.isovalue = updates.get('isovalue', obj.isovalue)
        obj.out_of_date = updates.get('out_of_date', obj.out_of_date)

    def set_out_of_date(self, names, out_of_date=True):
        for name in names:
            self.registry.get(name).out_of_date = out_of_date

    def out_of_date_objects(self):
        return self.registry.out_of_date()

    def render(self):
        pass


@pytest.fixture
def widget():
    model_manager = Mock()
    model_manager.model = None
    model_manager.features.return_value = []
    widget = FeatureListWidget(model_manager=model_manager, viewer=FakeViewer())
    widget._finish_isosurface_task = lambda: None
    return widget


def finish(widget, feature, existing, results):
    widget._pending_isosurface = (feature, existing)
    widget._on_isosurfaces_finished(results)


def test_five_isosurfaces_are_added_with_their_values(widget):
    values = [0.1, 0.3, 0.5, 0.7, 0.9]
    finish(widget, 'Fault_1', None, [(v, object(), None) for v in values])
    objects = widget.viewer.registry.of_feature('Fault_1', 'feature_isosurface')
    assert [o.name for o in objects] == [
        'Fault_1_iso_0.10',
        'Fault_1_iso_0.30',
        'Fault_1_iso_0.50',
        'Fault_1_iso_0.70',
        'Fault_1_iso_0.90',
    ]
    assert [o.isovalue for o in objects] == values


def test_a_value_outside_the_field_gives_a_message_not_an_error(widget):
    with patch('loopstructural.gui.visualisation.feature_list_widget.push_warning') as warning:
        finish(widget, 'Fault_1', None, [(0.5, object(), None), (99.0, None, 'no surface')])
    assert widget.viewer.registry.names() == ['Fault_1_iso_0.50']
    warning.assert_called_once()
    assert '99' in warning.call_args[0][1]


def test_changing_a_value_changes_only_that_object(widget):
    finish(widget, 'Fault_1', None, [(0.2, object(), None), (0.8, object(), None)])
    other = widget.viewer.registry.get('Fault_1_iso_0.80')
    other_mesh = other.mesh
    new_mesh = object()
    finish(widget, 'Fault_1', 'Fault_1_iso_0.20', [(0.4, new_mesh, None)])
    # the name has the new value
    assert 'Fault_1_iso_0.20' not in widget.viewer.registry
    changed = widget.viewer.registry.get('Fault_1_iso_0.40')
    assert changed.isovalue == 0.4
    assert changed.mesh is new_mesh
    assert other.isovalue == 0.8
    assert other.mesh is other_mesh


def test_a_surface_built_while_the_model_changed_is_out_of_date(widget):
    widget._isosurface_thread = object()  # a task is running
    widget._on_model_update('model_updated')
    widget._isosurface_thread = None
    widget._pending_isosurface = ('Fault_1', None)
    widget._on_isosurfaces_finished([(0.5, object(), None)])
    assert widget.viewer.registry.get('Fault_1_iso_0.50').out_of_date


def test_a_surface_built_without_a_change_is_up_to_date(widget):
    widget._model_changed_during_isosurface = False
    finish(widget, 'Fault_1', None, [(0.5, object(), None)])
    assert not widget.viewer.registry.get('Fault_1_iso_0.50').out_of_date
