"""The connection of the plugin to a running GeoViewer, with the ``loop_link`` package.

``push_model`` connects, sends the objects of the model, applies the plain
colours, removes the old objects of the last push, and closes the connection.
Nothing keeps the link open, so the plugin has no state to repair when the
viewer stops. The viewer keeps the scene.

``loop_link`` is an optional package. The import is inside the functions, so the
plugin starts without it and the push says what to install.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from .scene import Group, Item, Skipped

INSTALL_HINT = (
    "The loop_link package is not installed. Install it in the Python of QGIS "
    "with: pip install loop-link"
)


class LinkError(Exception):
    """The push failed. The text tells the user why."""


@dataclass
class PushSummary:
    """What happened in one push."""

    sent: int = 0
    removed: int = 0
    cancelled: bool = False
    # (object id, text) of each object that the plugin or loop_link did not send
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    # texts of the messages that the viewer refused, and of the colours that it refused
    refused: List[str] = field(default_factory=list)

    def summary(self) -> str:
        text = f"{self.sent} objects sent to GeoViewer"
        if self.removed:
            text += f", {self.removed} old objects removed"
        if self.skipped:
            text += f", {len(self.skipped)} objects skipped"
        if self.cancelled:
            text += ", stopped by the user"
        text += "."
        if self.refused:
            text += f" The viewer refused {len(self.refused)} messages."
        return text

    def details(self) -> List[str]:
        return [f"{object_id}: {text}" for object_id, text in self.skipped] + list(self.refused)


def import_loop_link():
    """Return the ``loop_link`` module, or raise a ``LinkError`` with the install hint."""
    try:
        import loop_link
    except ImportError as error:
        raise LinkError(INSTALL_HINT) from error
    return loop_link


def loop_link_available() -> bool:
    try:
        import_loop_link()
    except LinkError:
        return False
    return True


def push_model(
    items: Iterable[Any],
    *,
    crs: str = '',
    origin: Sequence[float] = (0.0, 0.0, 0.0),
    port: Optional[int] = None,
    token: Optional[str] = None,
    replace_prefix: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    cancel: Optional[threading.Event] = None,
    viewer=None,
) -> PushSummary:
    """Send the values of ``scene.model_items`` to the viewer.

    Parameters
    ----------
    items : iterable
        ``Group``, ``Item`` and ``Skipped`` values. The iterable is read while the
        objects are sent, so a slow object is built just before it is sent.
    crs, origin : the CRS and the origin that the plugin proposes for the scene.
        If the scene of the viewer has an origin already, the viewer keeps it.
    port, token : the port and the token of the viewer. ``None`` means that
        loop_link finds the viewer and reads the token (the ``GEOVIEWER_TOKEN``
        variable, or the token that the viewer saved).
    replace_prefix : after the push, remove the objects of the viewer whose id
        starts with this text and that were not sent again.
    progress : called with a text before each step.
    cancel : an event that stops the push before the next object.
    viewer : a ``loop_link.Viewer`` to use, for the tests. The function closes it.

    Raises
    ------
    LinkError
        The viewer cannot be reached, it refused the link, or nothing was sent.
    """
    loop_link = import_loop_link()
    if viewer is None:
        viewer = loop_link.Viewer(
            port=port or None, token=token or None, crs=crs or '', origin=origin
        )
    summary = PushSummary()
    colours: List[Tuple[str, Tuple[int, int, int]]] = []

    def objects():
        for value in items:
            if isinstance(value, Group):
                viewer.send_group(value.id, value.name, value.parent)
            elif isinstance(value, Skipped):
                summary.skipped.append((value.id, value.reason))
            elif isinstance(value, Item):
                if value.colour is not None:
                    colours.append((value.id, value.colour))
                yield (value.id, value.obj, {'name': value.name, 'parent': value.parent})

    try:
        viewer.connect()
        result = loop_link.push_objects(
            viewer,
            objects(),
            replace_prefix=replace_prefix,
            progress=progress,
            cancel=cancel,
        )
        summary.sent = result.sent
        summary.removed = result.removed
        summary.cancelled = result.cancelled
        summary.skipped += list(result.skipped)
        summary.refused += [f"{r.object_id}: {r.message}" for r in result.refused]
        _apply_colours(viewer, colours, {r.object_id for r in result.refused}, summary)
    except loop_link.LoopLinkError as error:
        raise LinkError(str(error)) from error
    finally:
        viewer.close()
    if summary.sent == 0 and not summary.cancelled:
        reasons = '; '.join(summary.details())
        raise LinkError("No object was sent to GeoViewer." + (f" {reasons}" if reasons else ""))
    return summary


def _apply_colours(viewer, colours, refused_ids, summary: PushSummary) -> None:
    """Give a plain colour to the objects that the viewer accepted.

    A viewer that is too old for the colour commands refuses the first one. The
    objects keep the colours of the viewer, and the summary says so once.
    """
    for object_id, colour in colours:
        if object_id in refused_ids:
            continue
        try:
            viewer.set_object_colour(object_id, colour)
        except Exception as error:
            summary.refused.append(f"{object_id}: colour not set ({error})")
            if type(error).__name__ == 'MissingFeatureError':
                return
