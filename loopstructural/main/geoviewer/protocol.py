"""The message format of the GeoViewer link (protocol 1.x).

No QGIS and no pyvista code, only the standard library and numpy. A message is
one binary frame:

    [u32 header_len][JSON header, UTF-8][buffer 0][buffer 1]...

All numbers are little-endian. The header lists the buffers in order. See
``docs/protocol.md`` in the GeoViewer repository for the full description.
"""

import json
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

PROTOCOL_VERSION = {'major': 1, 'minor': 8}

# The largest frame that the viewer accepts
MAX_FRAME_BYTES = 256 * 1024 * 1024
# Beyond this distance from the origin an f32 coordinate is not exact to 1 mm
F32_LIMIT = 4000.0

APPLICATION_NAME = 'plugin_loopstructural'


class ProtocolError(Exception):
    """A frame cannot be written or read."""


def encode_frame(header: Dict[str, Any], buffers: Sequence[Tuple[str, np.ndarray]] = ()) -> bytes:
    """Return the frame for a header and its named buffers.

    The function adds ``version`` and ``buffers`` to the header. A buffer is a
    ``(name, array)`` pair. The array must be f32, f64, u32, i32 or u8.
    """
    descriptions = []
    payload = []
    for name, array in buffers:
        array = np.ascontiguousarray(array)
        dtype = _DTYPE_NAMES.get(array.dtype.newbyteorder('<').str)
        if dtype is None:
            raise ProtocolError(f"Buffer {name!r} has the unsupported type {array.dtype}.")
        descriptions.append({'name': name, 'dtype': dtype, 'shape': list(array.shape)})
        payload.append(array.astype(array.dtype.newbyteorder('<'), copy=False).tobytes())
    full = dict(header)
    full['version'] = PROTOCOL_VERSION
    full['buffers'] = descriptions
    header_bytes = json.dumps(full, separators=(',', ':'), allow_nan=False).encode('utf-8')
    frame = b''.join([struct.pack('<I', len(header_bytes)), header_bytes, *payload])
    if len(frame) > MAX_FRAME_BYTES:
        raise ProtocolError(
            f"The message is {len(frame)} bytes. The viewer accepts {MAX_FRAME_BYTES} bytes at most."
        )
    return frame


_DTYPE_NAMES = {
    np.dtype('<f4').str: 'f32',
    np.dtype('<f8').str: 'f64',
    np.dtype('<u4').str: 'u32',
    np.dtype('<i4').str: 'i32',
    np.dtype('u1').str: 'u8',
}


def decode_header(frame: bytes) -> Dict[str, Any]:
    """Return the JSON header of a frame. The buffers are ignored."""
    if len(frame) < 4:
        raise ProtocolError("The frame is shorter than 4 bytes.")
    (length,) = struct.unpack_from('<I', frame, 0)
    if 4 + length > len(frame):
        raise ProtocolError("The frame stops inside the header.")
    try:
        return json.loads(frame[4 : 4 + length].decode('utf-8'))
    except ValueError as error:
        raise ProtocolError(f"The header is not valid JSON: {error}") from error


def hello_message(crs: str, origin: Sequence[float], version: str = '0') -> bytes:
    """Return the ``hello`` frame. ``origin`` is the origin of the scene in ``crs``."""
    return encode_frame(
        {
            'type': 'hello',
            'application': {'name': APPLICATION_NAME, 'version': version},
            'crs': crs,
            'origin': [float(v) for v in origin],
        }
    )


def clear_message() -> bytes:
    """Return the ``scene.clear`` frame."""
    return encode_frame({'type': 'scene.clear'})


def remove_message(object_id: str) -> bytes:
    """Return the ``scene.remove`` frame for an object or a group (with its children)."""
    return encode_frame({'type': 'scene.remove', 'id': object_id})


def _upsert_header(
    object_id: str,
    object_type: str,
    name: str,
    parent: Optional[str],
    revision: int,
    style: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        'type': 'scene.upsert',
        'id': object_id,
        'object_type': object_type,
        'name': name,
        'parent': parent,
        'revision': int(revision),
        'edit': [],
        'replaces': None,
        'geometry': {},
        'params': {},
        'data': [],
        'property_groups': [],
        'drape': None,
        'style': dict(style or {}),
    }


def group_message(
    object_id: str, name: str, parent: Optional[str] = None, revision: int = 1
) -> bytes:
    """Return the ``scene.upsert`` frame of a Group."""
    return encode_frame(_upsert_header(object_id, 'Group', name, parent, revision, None))


def surface_message(
    object_id: str,
    name: str,
    vertices,
    triangles,
    *,
    origin: Sequence[float] = (0.0, 0.0, 0.0),
    parent: Optional[str] = None,
    revision: int = 1,
    style: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Return the ``scene.upsert`` frame of a Surface.

    Parameters
    ----------
    vertices : array-like, shape (n, 3)
        The vertices in the coordinates of the CRS. The function subtracts
        ``origin`` in f64 and then writes f32, or f64 for a model that is more
        than 4 km from the origin.
    triangles : array-like, shape (m, 3)
        Vertex indices.
    """
    vertices = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    triangles = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if len(vertices) == 0 or len(triangles) == 0:
        raise ProtocolError(f"The surface {name!r} has no triangles.")
    if not np.isfinite(vertices).all():
        raise ProtocolError(f"The surface {name!r} has a vertex that is NaN or infinite.")
    if triangles.min() < 0 or triangles.max() >= len(vertices):
        raise ProtocolError(f"The surface {name!r} has a triangle index outside the vertices.")
    relative = vertices - np.asarray(origin, dtype=np.float64)
    if np.abs(relative).max() <= F32_LIMIT:
        relative = relative.astype(np.float32)
    header = _upsert_header(object_id, 'Surface', name, parent, revision, style)
    header['geometry'] = {'vertices': 'vertices', 'triangles': 'triangles'}
    return encode_frame(
        header,
        [('vertices', relative), ('triangles', triangles.astype(np.uint32))],
    )


def inventory_ids(header: Dict[str, Any]) -> List[str]:
    """Return the ids of a ``scene.inventory`` header."""
    return [entry['id'] for entry in header.get('entries', [])]
