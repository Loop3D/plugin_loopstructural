"""The connection of the plugin to a running GeoViewer.

``GeoViewerLink.push`` makes the connection, says ``hello``, sends the objects
of the model and closes the connection. Nothing keeps the link open, so the
plugin has no state to repair when the viewer stops. The viewer keeps the scene.
"""

from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from . import protocol
from .websocket_client import WebSocketClient, WebSocketClosed, WebSocketError

DEFAULT_PORT = 47615
HOST = '127.0.0.1'

# Time to wait for the answer to the hello message
_HELLO_TIMEOUT = 5.0
# Time to wait for the errors of the viewer after the last message
_SETTLE_TIMEOUT = 0.5


class LinkError(Exception):
    """The push failed. The text tells the user why."""


class PushResult:
    """What happened in one push."""

    def __init__(self):
        self.sent = 0
        self.removed = 0
        # (object id, text) of each error that the viewer sent about an object
        self.refused: List[Tuple[str, str]] = []
        self.other_errors: List[str] = []

    def summary(self) -> str:
        text = f"{self.sent} objects sent to GeoViewer"
        if self.removed:
            text += f", {self.removed} old objects removed"
        if self.refused or self.other_errors:
            text += f". The viewer refused {len(self.refused) + len(self.other_errors)} messages"
        return text + "."


class GeoViewerLink:
    """A short session with the viewer.

    Parameters
    ----------
    port, token : the port and the token of the link of the viewer. The viewer
        shows both in its link popup.
    """

    def __init__(self, port: int = DEFAULT_PORT, token: str = '', host: str = HOST):
        self.port = int(port)
        self.token = token or ''
        self.host = host

    def push(
        self,
        crs: str,
        origin: Sequence[float],
        build_messages: Callable[[Sequence[float]], Iterable[Tuple[str, bytes]]],
        *,
        replace_prefix: Optional[str] = None,
        progress: Optional[Callable[[str], None]] = None,
    ) -> PushResult:
        """Send objects to the viewer.

        Parameters
        ----------
        crs, origin : the CRS and the origin that the plugin proposes for the
            scene. If the scene of the viewer has an origin already, the viewer
            keeps it and says so in its ``hello`` answer.
        build_messages : called with the origin that the viewer uses. It yields
            ``(object id, frame)`` pairs. The coordinates must be relative to
            this origin.
        replace_prefix : after the push, remove the objects of the viewer whose
            id starts with this text and that were not sent again.
        progress : called with a text before each step.
        """
        say = progress or (lambda _text: None)
        say(f"Connecting to GeoViewer on port {self.port}...")
        try:
            client = WebSocketClient.connect(self.host, self.port, token=self.token)
        except WebSocketError as error:
            raise LinkError(
                f"{error} Start GeoViewer, and check the port and the token in its link popup."
            ) from error
        try:
            return self._session(client, crs, origin, build_messages, replace_prefix, say)
        except WebSocketError as error:
            raise LinkError(str(error)) from error
        finally:
            client.close()

    def _session(self, client, crs, origin, build_messages, replace_prefix, say) -> PushResult:
        result = PushResult()
        client.send_binary(protocol.hello_message(crs, origin))
        scene_origin, existing = self._read_hello_answer(client, origin)
        sent_ids = set()
        for object_id, frame in build_messages(scene_origin):
            say(f"Sending {object_id}...")
            client.send_binary(frame)
            sent_ids.add(object_id)
            result.sent += 1
            self._collect_errors(client, result, wait=0.0)
        if replace_prefix:
            for object_id in existing:
                if object_id.startswith(replace_prefix) and object_id not in sent_ids:
                    client.send_binary(protocol.remove_message(object_id))
                    result.removed += 1
        self._collect_errors(client, result, wait=_SETTLE_TIMEOUT)
        return result

    @staticmethod
    def _read_hello_answer(client, origin):
        """Return the origin of the scene and the ids that are in the scene.

        The viewer answers ``hello`` with its own ``hello`` and then with one
        ``scene.inventory``.
        """
        scene_origin = [float(v) for v in origin]
        ids: List[str] = []
        got_hello = got_inventory = False
        while not (got_hello and got_inventory):
            data = client.receive(_HELLO_TIMEOUT)
            if data is None:
                raise LinkError("GeoViewer did not answer the hello message.")
            header = protocol.decode_header(data)
            kind = header.get('type')
            if kind == 'hello':
                scene_origin = [float(v) for v in header.get('origin', scene_origin)]
                got_hello = True
            elif kind == 'scene.inventory':
                ids = protocol.inventory_ids(header)
                got_inventory = True
            elif kind == 'error':
                raise LinkError(f"GeoViewer refused the link: {header.get('message', '')}")
        return scene_origin, ids

    @staticmethod
    def _collect_errors(client, result: PushResult, *, wait: float):
        """Read the messages that wait in the socket and keep the errors."""
        while True:
            try:
                data = client.receive(wait if wait > 0 else 0.001)
            except WebSocketClosed:
                return
            if data is None:
                return
            header = protocol.decode_header(data)
            if header.get('type') != 'error':
                continue
            text = header.get('message', header.get('code', 'error'))
            if header.get('object'):
                result.refused.append((header['object'], text))
            else:
                result.other_errors.append(text)
