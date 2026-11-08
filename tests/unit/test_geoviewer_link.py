"""Tests for the push with loop_link (main/geoviewer/link.py).

The fake viewer of loop_link plays the part of GeoViewer on 127.0.0.1.
"""

import threading

import numpy as np
import pytest

loop_link = pytest.importorskip('loop_link')
from loop_link.testing import FakeViewer

from loopstructural.main.geoviewer import link
from loopstructural.main.geoviewer.link import LinkError, push_model
from loopstructural.main.geoviewer.scene import Group, Item, Skipped


@pytest.fixture
def fake(monkeypatch):
    # no variable of the developer can reach the tests
    monkeypatch.delenv('GEOVIEWER_TOKEN', raising=False)
    viewer = FakeViewer()
    yield viewer
    viewer.close()


def points(offset=0.0):
    return loop_link.Points(np.array([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]]) + offset)


def push(fake, items, **options):
    return push_model(items, port=fake.port, token='secret', **options)


def test_nothing_listens():
    unused = FakeViewer()
    port = unused.port
    unused.close()
    with pytest.raises(LinkError):
        push_model([Group('g', 'g', None), Item('a', points(), 'a', 'g')], port=port, token='x')


def test_wrong_token_is_refused(fake):
    with pytest.raises(LinkError):
        push_model([Item('a', points(), 'a', None)], port=fake.port, token='wrong')


def test_objects_and_groups_arrive_with_names_and_parents(fake):
    items = [
        Group('loopstructural/model', 'LoopStructural model', None),
        Group('loopstructural/model/points', 'Data points', 'loopstructural/model'),
        Item('loopstructural/model/points/a', points(), 'A', 'loopstructural/model/points'),
        Skipped('loopstructural/model/points/b', 'no values'),
    ]
    summary = push(fake, items, crs='EPSG:28350', origin=(1.0, 2.0, 0.0))
    assert summary.sent == 1
    assert summary.skipped == [('loopstructural/model/points/b', 'no values')]
    assert set(fake.objects) >= {'loopstructural/model/points/a', 'loopstructural/model/points'}
    header = fake.objects['loopstructural/model/points/a'].header
    assert header['name'] == 'A'
    assert header['parent'] == 'loopstructural/model/points'
    assert 'objects sent to GeoViewer' in summary.summary()


def test_plain_colour_is_applied(fake):
    push(fake, [Item('a', points(), 'a', None, colour=(10, 20, 30))])
    assert list(fake.colouring['a']['plain']) == [10, 20, 30]


def test_viewer_without_colour_commands_does_not_stop_the_push(fake, monkeypatch):
    viewer = loop_link.Viewer(port=fake.port, token='secret')

    def refuse(object_id, colour):
        raise loop_link.MissingFeatureError('colour')

    monkeypatch.setattr(viewer, 'set_object_colour', refuse)
    items = [
        Item('a', points(), 'a', None, colour=(1, 2, 3)),
        Item('b', points(), 'b', None, colour=(1, 2, 3)),
    ]
    summary = push_model(items, viewer=viewer)
    assert summary.sent == 2
    # the first refusal ends the colours, and the summary says so once
    assert len([t for t in summary.refused if 'colour not set' in t]) == 1


def test_old_objects_with_the_prefix_are_removed_and_other_objects_stay(fake):
    push(
        fake,
        [Item('loopstructural/old', points(), 'old', None), Item('other', points(), 'o', None)],
    )
    summary = push(
        fake, [Item('loopstructural/new', points(), 'new', None)], replace_prefix='loopstructural/'
    )
    assert summary.removed == 1
    assert 'loopstructural/old' not in fake.objects
    assert {'loopstructural/new', 'other'} <= set(fake.objects)


def test_refused_object_is_reported():
    refusing = FakeViewer(reply_errors={'a': 'too big'})
    try:
        summary = push_model(
            [Item('a', points(), 'a', None, colour=(1, 2, 3)), Item('b', points(), 'b', None)],
            port=refusing.port,
            token='secret',
        )
    finally:
        refusing.close()
    assert any('too big' in text for text in summary.refused)


def test_items_are_read_while_they_are_sent(fake):
    order = []

    def items():
        order.append('first made')
        yield Item('a', points(), 'a', None)
        order.append('second made')
        yield Item('b', points(), 'b', None)

    push(fake, items(), progress=order.append)
    assert order.index('Sending a...') < order.index('second made')


def test_cancel_stops_before_the_next_object_and_keeps_old_objects(fake):
    push(fake, [Item('loopstructural/old', points(), 'old', None)])
    cancel = threading.Event()

    def items():
        yield Item('loopstructural/a', points(), 'a', None)
        cancel.set()
        yield Item('loopstructural/b', points(), 'b', None)

    summary = push(fake, items(), replace_prefix='loopstructural/', cancel=cancel)
    assert summary.cancelled and summary.sent == 1 and summary.removed == 0
    assert 'loopstructural/old' in fake.objects


def test_nothing_sent_is_an_error_with_the_reasons(fake):
    with pytest.raises(LinkError, match='no values'):
        push(fake, [Group('g', 'g', None), Skipped('g/a', 'no values')])


def test_missing_loop_link_gives_the_install_hint(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fail(name, *args, **kwargs):
        if name == 'loop_link':
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', fail)
    assert not link.loop_link_available()
    with pytest.raises(LinkError, match='pip install loop-link'):
        push_model([])
