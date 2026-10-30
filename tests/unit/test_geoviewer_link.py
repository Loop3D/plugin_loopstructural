"""Tests for the WebSocket client and the push session (main/geoviewer/link.py).

A fake viewer on 127.0.0.1 plays the part of GeoViewer.
"""

import pytest

from loopstructural.main.geoviewer import protocol
from loopstructural.main.geoviewer.link import GeoViewerLink, LinkError, SkippedObject
from loopstructural.main.geoviewer.websocket_client import WebSocketClient, WebSocketError

from .geoviewer_fake_server import FakeViewer


@pytest.fixture
def viewer():
    fake = FakeViewer()
    yield fake
    fake.close()


def triangle(object_id):
    return protocol.surface_message(
        object_id, object_id, [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]]
    )


def test_wrong_token_is_refused(viewer):
    with pytest.raises(WebSocketError, match='token'):
        WebSocketClient.connect('127.0.0.1', viewer.port, token='wrong')


def test_nothing_listens():
    fake = FakeViewer()
    port = fake.port
    fake.close()
    with pytest.raises(LinkError, match='Cannot connect'):
        GeoViewerLink(port, 'secret').push('EPSG:1', (0, 0, 0), lambda origin: [])


def test_push_says_hello_and_sends_the_objects(viewer):
    seen_origin = []

    def build(origin):
        seen_origin.append(list(origin))
        yield 'a', triangle('a')
        yield 'b', triangle('b')

    result = GeoViewerLink(viewer.port, 'secret').push('EPSG:28350', (1, 2, 3), build)
    assert viewer.types() == ['hello', 'scene.upsert', 'scene.upsert']
    assert viewer.headers('hello')[0]['origin'] == [1.0, 2.0, 3.0]
    assert viewer.headers('hello')[0]['crs'] == 'EPSG:28350'
    # the viewer origin applies, not the origin that the plugin proposed
    assert seen_origin == [[10.0, 20.0, 0.0]]
    assert result.sent == 2 and result.removed == 0 and not result.refused


def test_push_removes_old_objects_with_the_prefix_only():
    fake = FakeViewer(inventory=['loopstructural/old', 'loopstructural/keep', 'other/file'])
    try:
        result = GeoViewerLink(fake.port, 'secret').push(
            'EPSG:1',
            (0, 0, 0),
            lambda origin: [('loopstructural/keep', triangle('loopstructural/keep'))],
            replace_prefix='loopstructural/',
        )
    finally:
        fake.close()
    assert [h['id'] for h in fake.headers('scene.remove')] == ['loopstructural/old']
    assert result.removed == 1


def test_refused_object_is_reported():
    fake = FakeViewer(reply_errors={'a': 'the surface is not valid'})
    try:
        result = GeoViewerLink(fake.port, 'secret').push(
            'EPSG:1', (0, 0, 0), lambda origin: [('a', triangle('a')), ('b', triangle('b'))]
        )
    finally:
        fake.close()
    assert result.sent == 2
    assert result.refused == [('a', 'the surface is not valid')]
    assert '1 messages' in result.summary()


def test_large_message_is_sent_whole(viewer):
    import numpy as np

    count = 40000
    vertices = np.random.default_rng(0).random((count, 3)) * 100
    triangles = np.arange(count - count % 3).reshape(-1, 3)
    frame = protocol.surface_message('big', 'big', vertices, triangles)
    GeoViewerLink(viewer.port, 'secret').push('EPSG:1', (0, 0, 0), lambda origin: [('big', frame)])
    assert viewer.received[-1][1] == frame


def test_a_large_surface_after_a_small_one_is_sent_whole():
    # After the small object, the client looks for errors with a short wait.
    # The large frame must not use that wait as its send timeout.
    import numpy as np

    fake = FakeViewer(read_delay=0.3)
    try:
        count = 1_000_000
        vertices = np.random.default_rng(0).random((count, 3)) * 100
        triangles = np.arange(count - count % 3).reshape(-1, 3)
        big = protocol.surface_message('big', 'big', vertices, triangles)
        GeoViewerLink(fake.port, 'secret').push(
            'EPSG:1', (0, 0, 0), lambda origin: [('small', triangle('small')), ('big', big)]
        )
        fake._thread.join(30)  # the fake reads slowly
    finally:
        fake.close()
    assert fake.received[-1][1] == big


def test_a_null_origin_uses_the_proposed_origin():
    fake = FakeViewer(origin=None)
    used = []

    def build(origin):
        used.append(list(origin))
        return [('a', triangle('a'))]

    try:
        GeoViewerLink(fake.port, 'secret').push('EPSG:1', (5, 6, 0), build)
    finally:
        fake.close()
    assert used == [[5.0, 6.0, 0.0]]


def test_a_skipped_object_is_recorded_and_the_push_continues(viewer):
    result = GeoViewerLink(viewer.port, 'secret').push(
        'EPSG:1',
        (0, 0, 0),
        lambda origin: [('bad', SkippedObject('no mesh')), ('a', triangle('a'))],
    )
    assert result.sent == 1
    assert result.skipped == [('bad', 'no mesh')]
    assert '1 objects skipped' in result.summary()


def test_a_timeout_in_the_middle_of_a_frame_closes_the_link(monkeypatch):
    import socket

    from loopstructural.main.geoviewer import websocket_client

    monkeypatch.setattr(websocket_client, '_FRAME_TIMEOUT', 0.1)
    ours, theirs = socket.socketpair()
    try:
        client = WebSocketClient(ours)
        assert client.receive(0.05) is None  # nothing arrived: the link stays open
        assert not client.closed
        theirs.sendall(bytes([0x82, 10]) + b'abc')  # 3 of 10 bytes
        with pytest.raises(WebSocketError, match='middle'):
            client.receive(1.0)
        assert client.closed
    finally:
        theirs.close()
        ours.close()


class _TimeoutCheckingSocket:
    """A socket that fails if a send has a timeout too short for a large frame."""

    def __init__(self, sock):
        self._sock = sock
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout
        self._sock.settimeout(timeout)

    def sendall(self, data):
        assert self.timeout is None or self.timeout >= 1.0, f"send timeout {self.timeout}"
        self._sock.sendall(data)

    def __getattr__(self, name):
        return getattr(self._sock, name)


def test_a_send_after_a_short_receive_has_a_long_timeout():
    import socket

    ours, theirs = socket.socketpair()
    try:
        client = WebSocketClient(_TimeoutCheckingSocket(ours))
        assert client.receive(0.001) is None  # leaves a 1 ms timeout on the socket
        client.send_binary(b'x' * 1000)
    finally:
        theirs.close()
        ours.close()
