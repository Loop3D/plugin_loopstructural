"""Pytest tests for the keys of the sections in `SectionStack`."""

from qgis.gui import QgsCollapsibleGroupBox
from qgis.testing import start_app

start_app()

from loopstructural.gui.modelling.steps.section_stack import SectionStack


def test_two_group_boxes_with_the_same_title_are_two_sections():
    stack = SectionStack(name='test')
    first = QgsCollapsibleGroupBox("Interpolator")
    second = QgsCollapsibleGroupBox("Interpolator")
    stack.addWidget(first)
    stack.addWidget(second)
    assert stack.section('Interpolator') is first
    assert stack.section('Interpolator_2') is second


def test_the_object_name_is_the_key():
    stack = SectionStack(name='test')
    group = QgsCollapsibleGroupBox("Interpolator")
    group.setObjectName('interpolator')
    stack.addWidget(group)
    assert stack.section('interpolator') is group
