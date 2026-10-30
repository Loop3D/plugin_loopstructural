"""Turn the results of a solved model into the objects of the GeoViewer scene.

The functions do not import QGIS. They read the model through the model manager
(``model`` with ``get_stratigraphic_surfaces`` and ``get_fault_surfaces``).
"""

import time
from typing import Iterator, List, Optional, Sequence, Tuple

import numpy as np

from . import protocol
from .link import SkippedObject

# Every object of the plugin has an id that starts with this text, so that a new
# push can replace the objects of the old push.
ID_PREFIX = 'loopstructural/'
ROOT_ID = ID_PREFIX + 'model'
STRATIGRAPHY_ID = ROOT_ID + '/stratigraphy'
FAULTS_ID = ROOT_ID + '/faults'

# A fault is drawn in a different colour than the units: dark red
FAULT_COLOUR = [200, 40, 40, 255]


class PushError(Exception):
    """The model cannot be pushed, for example because it is not solved."""


def proposed_origin(model) -> List[float]:
    """Return the centre of the bounding box of the model, with z = 0.

    The viewer uses it as the origin of the scene when its scene is empty.
    The values are rounded to whole metres, so the origin is easy to read.
    """
    box = model.bounding_box
    centre = (np.asarray(box.origin, dtype=float) + np.asarray(box.maximum, dtype=float)) / 2.0
    return [float(round(centre[0])), float(round(centre[1])), 0.0]


def triangles_of(mesh) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(vertices, triangles)`` of a pyvista surface mesh."""
    mesh = mesh.triangulate()
    vertices = np.asarray(mesh.points, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if faces.size == 0:
        return vertices, np.zeros((0, 3), dtype=np.int64)
    return vertices, faces.reshape(-1, 4)[:, 1:]


def _surfaces(model, stratigraphic: bool, faults: bool):
    result = []
    if stratigraphic:
        result += [('stratigraphy', s) for s in model.get_stratigraphic_surfaces()]
    if faults:
        result += [('faults', s) for s in model.get_fault_surfaces()]
    return result


def _unique_id(base: str, used: set) -> str:
    candidate, count = base, 1
    while candidate in used:
        count += 1
        candidate = f"{base}_{count}"
    used.add(candidate)
    return candidate


def model_messages(
    model_manager,
    origin: Sequence[float],
    *,
    stratigraphic: bool = True,
    faults: bool = True,
    revision: Optional[int] = None,
    progress=None,
) -> Iterator[Tuple[str, bytes]]:
    """Yield ``(object id, frame)`` for the groups and the surfaces of the model.

    The groups come first, so the viewer knows the parent of each surface. A
    surface with no triangles is skipped, as in the file export. A surface that
    cannot be read gives a ``SkippedObject`` in place of its frame.
    """
    model = getattr(model_manager, 'model', None)
    if model is None:
        raise PushError("There is no model to push. Build the model in step 4 first.")
    revision = int(time.time()) if revision is None else int(revision)
    surfaces = _surfaces(model, stratigraphic, faults)
    if not surfaces:
        raise PushError("The model has no surfaces to push.")

    kinds = {kind for kind, _ in surfaces}
    yield ROOT_ID, protocol.group_message(ROOT_ID, 'LoopStructural model', None, revision)
    if 'stratigraphy' in kinds:
        yield STRATIGRAPHY_ID, protocol.group_message(
            STRATIGRAPHY_ID, 'Stratigraphic surfaces', ROOT_ID, revision
        )
    if 'faults' in kinds:
        yield FAULTS_ID, protocol.group_message(FAULTS_ID, 'Fault surfaces', ROOT_ID, revision)

    used = set()
    pushed = 0
    skipped = []
    for kind, surface in surfaces:
        if progress is not None:
            progress(f"Reading {surface.name}...")
        parent = STRATIGRAPHY_ID if kind == 'stratigraphy' else FAULTS_ID
        object_id = _unique_id(f"{parent}/{surface.name}", used)
        # one bad surface does not stop the push of the others
        try:
            vertices, triangles = triangles_of(surface.vtk())
            if len(triangles) == 0:
                continue
            style = {'colour': FAULT_COLOUR} if kind == 'faults' else None
            frame = protocol.surface_message(
                object_id,
                str(surface.name),
                vertices,
                triangles,
                origin=origin,
                parent=parent,
                revision=revision,
                style=style,
            )
        except Exception as error:
            skipped.append(f"{surface.name}: {error}")
            yield object_id, SkippedObject(str(error))
            continue
        yield object_id, frame
        pushed += 1
    if pushed == 0:
        if skipped:
            raise PushError("No surface could be read: " + "; ".join(skipped))
        raise PushError("All surfaces are empty. Check the bounding box and the data.")
