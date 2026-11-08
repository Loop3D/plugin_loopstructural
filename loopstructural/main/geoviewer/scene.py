"""Turn a solved model into the objects that loop_link sends to GeoViewer.

The functions do not import QGIS or loop_link at module level. ``loop_link`` is
an optional package, so the import is inside the functions that need it. They
read the model through the model manager (``model``, ``sample_dem_grid`` and the
stratigraphy helpers).

``model_items`` yields three kinds of values:

* ``Group``: a group of the scene. It always comes before its children.
* ``Item``: an object to send, in world coordinates. The link subtracts the
  origin of the scene.
* ``Skipped``: an object that the plugin could not make. The push continues.
"""

from typing import Callable, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np

# Every object of the plugin has an id that starts with this text, so that a new
# push can replace the objects of the old push.
ID_PREFIX = 'loopstructural/'
ROOT_ID = ID_PREFIX + 'model'

# The kinds of object that a push can send: key -> (label, group id)
KINDS: Dict[str, Tuple[str, str]] = {
    'stratigraphy_surfaces': ('Stratigraphic surfaces', ROOT_ID + '/stratigraphy'),
    'fault_surfaces': ('Fault surfaces', ROOT_ID + '/faults'),
    'stratigraphy_volume': ('Stratigraphy volume', ROOT_ID + '/volume'),
    'scalar_fields': ('Scalar fields', ROOT_ID + '/scalar_fields'),
    'dem': ('DEM', ROOT_ID + '/dem'),
    'points': ('Data points', ROOT_ID + '/points'),
    'vectors': ('Orientation data', ROOT_ID + '/vectors'),
    'vector_fields': ('Vector fields', ROOT_ID + '/vector_fields'),
    'lines': ('Lines', ROOT_ID + '/lines'),
}
ALL_KINDS = tuple(KINDS)

# A fault is drawn in a different colour than the units: dark red
FAULT_COLOUR = (200, 40, 40)
NO_UNIT_NAME = 'No unit'
NO_UNIT_COLOUR = (153, 153, 153, 255)

# A vector field has at most this number of vectors, so that the viewer stays fast
MAX_VECTOR_FIELD_POINTS = 20000
DEFAULT_CELLS = (50, 50, 25)
DEFAULT_DEM_RESOLUTION = 100


class PushError(Exception):
    """The model cannot be pushed, for example because it is not solved."""


class Group(NamedTuple):
    id: str
    name: str
    parent: Optional[str]


class Item(NamedTuple):
    """An object to send. ``colour`` is an optional plain RGB colour for the object."""

    id: str
    obj: object
    name: str
    parent: Optional[str]
    colour: Optional[Tuple[int, int, int]] = None


class Skipped(NamedTuple):
    """An object that could not be made. ``reason`` tells the user why."""

    id: str
    reason: str


class LineSet(NamedTuple):
    """The lines of one layer: ``polylines`` is a list of (n, 3) arrays."""

    key: str
    name: str
    polylines: List[np.ndarray]


def proposed_origin(model) -> List[float]:
    """Return the centre of the bounding box of the model, with z = 0.

    The viewer uses it as the origin of the scene when its scene is empty.
    The values are rounded to whole metres, so the origin is easy to read.
    """
    box = model.bounding_box
    centre = (np.asarray(box.origin, dtype=float) + np.asarray(box.maximum, dtype=float)) / 2.0
    return [float(round(centre[0])), float(round(centre[1])), 0.0]


# -- geometry helpers ------------------------------------------------------


def triangles_of(mesh) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(vertices, triangles)`` of a pyvista surface mesh."""
    mesh = mesh.triangulate()
    vertices = np.asarray(mesh.points, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if faces.size == 0:
        return vertices, np.zeros((0, 3), dtype=np.int64)
    return vertices, faces.reshape(-1, 4)[:, 1:]


def compact_triangles(vertices: np.ndarray, triangles: np.ndarray):
    """Drop the triangles that use a vertex that is not finite, and the unused vertices.

    Returns ``(vertices, triangles)``.
    """
    finite = np.all(np.isfinite(vertices), axis=1)
    if len(triangles):
        triangles = triangles[np.all(finite[triangles], axis=1)]
    used = np.unique(triangles) if len(triangles) else np.zeros(0, dtype=np.int64)
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return vertices[used], remap[triangles]


def grid_triangles(rows: int, columns: int) -> np.ndarray:
    """Return the triangles of a regular grid of ``rows * columns`` vertices.

    The vertices are in row order. The triangles turn counter-clockwise when seen
    from above (x to the right, y up), so the normal points up.
    """
    index = np.arange(rows * columns).reshape(rows, columns)
    a = index[:-1, :-1].ravel()
    b = index[:-1, 1:].ravel()
    c = index[1:, 1:].ravel()
    d = index[1:, :-1].ravel()
    return np.concatenate([np.column_stack([a, b, c]), np.column_stack([a, c, d])])


def grid_points(axes: Sequence[np.ndarray]) -> np.ndarray:
    """Return the points of a grid with the x axis changing fastest."""
    grids = np.meshgrid(*axes, indexing='ij')
    return np.column_stack([g.ravel(order='F') for g in grids])


def rgb_of(colour) -> Optional[Tuple[int, int, int]]:
    """Return a colour of any matplotlib form as ``(r, g, b)`` of 0 to 255, or None."""
    if colour is None:
        return None
    try:
        from matplotlib.colors import to_rgb

        return tuple(int(round(v * 255)) for v in to_rgb(colour))
    except (ValueError, TypeError, ImportError):
        return None


def rgba_of(colour) -> Tuple[int, int, int, int]:
    rgb = rgb_of(colour)
    return (*rgb, 255) if rgb is not None else NO_UNIT_COLOUR


def unique_id(base: str, used: set) -> str:
    candidate, count = base, 1
    while candidate in used:
        count += 1
        candidate = f"{base}_{count}"
    used.add(candidate)
    return candidate


def world_locations(model, locations) -> np.ndarray:
    """Return the locations of feature data in world coordinates.

    Some versions of LoopStructural give the data in model coordinates and some in
    world coordinates, so use the version that is nearer to the centre of the model.
    """
    raw = np.asarray(locations, dtype=float)
    if raw.size == 0:
        return raw.reshape(0, 3)
    box = model.bounding_box
    centre = (np.asarray(box.origin, dtype=float) + np.asarray(box.maximum, dtype=float)) / 2.0
    try:
        scaled = np.asarray(model.rescale(raw), dtype=float)
    except Exception:
        return raw
    if np.linalg.norm(np.nanmean(scaled, axis=0) - centre) < np.linalg.norm(
        np.nanmean(raw, axis=0) - centre
    ):
        return scaled
    return raw


def _grid_of(model, ncells) -> Tuple[np.ndarray, np.ndarray]:
    """Return the origin and the cell size of a grid that fills the bounding box."""
    box = model.bounding_box
    origin = np.asarray(box.origin, dtype=float)
    size = (np.asarray(box.maximum, dtype=float) - origin) / np.asarray(ncells, dtype=float)
    return origin, size


# -- the objects of each kind ----------------------------------------------


def _feature_names(model) -> List[str]:
    return [str(f.name) for f in model.features if not str(f.name).startswith('__')]


def _surface_items(model, kind: str, used: set) -> Iterator[object]:
    from loop_link import Surface

    group = KINDS[kind][1]
    stratigraphic = kind == 'stratigraphy_surfaces'
    surfaces = model.get_stratigraphic_surfaces() if stratigraphic else model.get_fault_surfaces()
    for surface in surfaces:
        object_id = unique_id(f"{group}/{surface.name}", used)
        try:
            vertices, triangles = triangles_of(surface.vtk())
            if len(triangles) == 0:
                continue
            obj = Surface(vertices=vertices, triangles=triangles)
        except Exception as error:
            yield Skipped(object_id, f"{surface.name}: {error}")
            continue
        colour = FAULT_COLOUR if not stratigraphic else rgb_of(getattr(surface, 'colour', None))
        yield Item(object_id, obj, str(surface.name), group, colour)


def _volume_items(model_manager, ncells, used: set) -> Iterator[object]:
    from loop_link import BlockModel, Categorical

    group = KINDS['stratigraphy_volume'][1]
    object_id = unique_id(f"{group}/stratigraphy", used)
    names = list(model_manager.get_stratigraphic_unit_names())
    if not names:
        yield Skipped(object_id, "The model has no stratigraphic units.")
        return
    origin, size = _grid_of(model_manager.model, ncells)
    centres = grid_points([origin[i] + (np.arange(ncells[i]) + 0.5) * size[i] for i in range(3)])
    ids = np.asarray(model_manager.evaluate_stratigraphy_on_points(centres)).astype(int)
    count = len(names)
    codes = np.where((ids >= 0) & (ids < count), ids, count)
    colours = [rgba_of(c) for c in model_manager.get_stratigraphic_column_colours()]
    colours = (colours + [NO_UNIT_COLOUR] * count)[:count] + [NO_UNIT_COLOUR]
    unit = Categorical(codes=codes, names=names + [NO_UNIT_NAME], colours=colours)
    yield Item(
        object_id,
        BlockModel(origin=origin, cell_sizes=size, cells=ncells, cell_properties={'unit': unit}),
        'Stratigraphy',
        group,
    )


def _scalar_field_items(model, ncells, used: set, progress) -> Iterator[object]:
    from loop_link import BlockModel

    group = KINDS['scalar_fields'][1]
    origin, size = _grid_of(model, ncells)
    nodes = grid_points([origin[i] + np.arange(ncells[i] + 1) * size[i] for i in range(3)])
    for name in _feature_names(model):
        object_id = unique_id(f"{group}/{name}", used)
        if progress is not None:
            progress(f"Evaluating {name}...")
        try:
            values = np.asarray(model.evaluate_feature_value(name, nodes), dtype=float)
            if values.shape != (len(nodes),):
                raise ValueError("the feature gives no scalar value")
            obj = BlockModel(
                origin=origin, cell_sizes=size, cells=ncells, properties={'value': values}
            )
        except Exception as error:
            yield Skipped(object_id, f"{name}: {error}")
            continue
        yield Item(object_id, obj, name, group)


def _dem_items(model_manager, resolution: int, used: set) -> Iterator[object]:
    from loop_link import Surface

    group = KINDS['dem'][1]
    object_id = unique_id(f"{group}/dem", used)
    try:
        xx, yy, zz = model_manager.sample_dem_grid(resolution)
        vertices = np.column_stack([np.ravel(xx), np.ravel(yy), np.ravel(zz)]).astype(float)
        vertices, triangles = compact_triangles(vertices, grid_triangles(*np.shape(xx)))
        if len(triangles) == 0:
            raise ValueError("the DEM has no values in the model area")
        obj = Surface(
            vertices=vertices, triangles=triangles, properties={'elevation': vertices[:, 2]}
        )
    except Exception as error:
        yield Skipped(object_id, f"DEM: {error}")
        return
    yield Item(object_id, obj, 'DEM', group)


def _data_items(model, kind: str, used: set) -> Iterator[object]:
    """The input data of the features: points, or orientation vectors."""
    from loop_link import Points, Vectors

    want_vectors = kind == 'vectors'
    group = KINDS[kind][1]
    for name in _feature_names(model):
        try:
            datasets = list(model[name].get_data())
        except Exception as error:
            yield Skipped(f"{group}/{name}", f"{name}: {error}")
            continue
        for data in datasets:
            is_vector = hasattr(data, 'vectors')
            if is_vector != want_vectors:
                continue
            label = str(getattr(data, 'name', name)).replace('+_', '_')
            object_id = unique_id(f"{group}/{name}/{label}", used)
            try:
                locations = world_locations(model, data.locations)
                if is_vector:
                    vectors = np.asarray(data.vectors, dtype=float)
                    keep = (
                        np.all(np.isfinite(locations), axis=1)
                        & np.all(np.isfinite(vectors), axis=1)
                        & (np.linalg.norm(vectors, axis=1) > 0)
                    )
                    if not keep.any():
                        continue
                    kind_of_vector = 'lineation' if 'tangent' in label else 'normal'
                    obj = Vectors.from_directions(
                        locations[keep], vectors[keep], kind=kind_of_vector
                    )
                else:
                    values = np.asarray(data.values, dtype=float).reshape(-1)
                    keep = np.all(np.isfinite(locations), axis=1)
                    if not keep.any():
                        continue
                    properties = {'value': values[keep]} if len(values) == len(keep) else {}
                    obj = Points(locations[keep], properties=properties)
            except Exception as error:
                yield Skipped(object_id, f"{label}: {error}")
                continue
            yield Item(object_id, obj, label, group)


def _vector_field_items(model, used: set, progress) -> Iterator[object]:
    """The gradient of each feature on the grid of the model."""
    from loop_link import Vectors

    group = KINDS['vector_fields'][1]
    for name in _feature_names(model):
        object_id = unique_id(f"{group}/{name}", used)
        if progress is not None:
            progress(f"Evaluating the gradient of {name}...")
        try:
            field = model[name].vector_field()
            locations = np.asarray(field.locations, dtype=float)
            vectors = np.asarray(field.vectors, dtype=float)
            keep = (
                np.all(np.isfinite(locations), axis=1)
                & np.all(np.isfinite(vectors), axis=1)
                & (np.linalg.norm(vectors, axis=1) > 0)
            )
            locations, vectors = locations[keep], vectors[keep]
            if len(locations) > MAX_VECTOR_FIELD_POINTS:
                step = int(np.ceil(len(locations) / MAX_VECTOR_FIELD_POINTS))
                locations, vectors = locations[::step], vectors[::step]
            if len(locations) == 0:
                raise ValueError("the gradient is not defined")
            obj = Vectors.from_directions(locations, vectors, kind='normal')
        except Exception as error:
            yield Skipped(object_id, f"{name}: {error}")
            continue
        yield Item(object_id, obj, name, group)


def lines_from_polylines(polylines: Iterable[np.ndarray]):
    """Return a loop_link ``Lines`` object for a list of polylines of (n, 3) points."""
    from loop_link import Lines

    vertices, segments, offset = [], [], 0
    for line in polylines:
        line = np.asarray(line, dtype=float)
        if line.ndim != 2 or line.shape[1] != 3:
            continue
        line = line[np.all(np.isfinite(line), axis=1)]
        if len(line) < 2:
            continue
        vertices.append(line)
        count = len(line)
        segments.append(np.column_stack([np.arange(count - 1), np.arange(1, count)]) + offset)
        offset += count
    if not vertices:
        raise ValueError("there are no lines")
    return Lines(vertices=np.concatenate(vertices), segments=np.concatenate(segments))


def bounding_box_polylines(model) -> List[np.ndarray]:
    """Return the 12 edges of the bounding box of the model."""
    low = np.asarray(model.bounding_box.origin, dtype=float)
    high = np.asarray(model.bounding_box.maximum, dtype=float)
    corners = np.array([[(high if (i >> k) & 1 else low)[k] for k in range(3)] for i in range(8)])
    edges = [(i, i | (1 << k)) for i in range(8) for k in range(3) if not (i >> k) & 1]
    return [corners[list(edge)] for edge in edges]


def _line_items(model, line_sets: Sequence[LineSet], used: set) -> Iterator[object]:
    group = KINDS['lines'][1]
    sets = [LineSet('bounding_box', 'Bounding box', bounding_box_polylines(model))]
    sets += list(line_sets)
    for line_set in sets:
        object_id = unique_id(f"{group}/{line_set.key}", used)
        try:
            obj = lines_from_polylines(line_set.polylines)
        except Exception as error:
            yield Skipped(object_id, f"{line_set.name}: {error}")
            continue
        yield Item(object_id, obj, line_set.name, group)


# -- the whole model -------------------------------------------------------


def model_items(
    model_manager,
    kinds: Iterable[str] = ALL_KINDS,
    *,
    ncells: Sequence[int] = DEFAULT_CELLS,
    dem_resolution: int = DEFAULT_DEM_RESOLUTION,
    line_sets: Sequence[LineSet] = (),
    progress: Optional[Callable[[str], None]] = None,
) -> Iterator[object]:
    """Yield the ``Group``, ``Item`` and ``Skipped`` values of the model.

    Parameters
    ----------
    kinds : keys of `KINDS`
        Which kinds of object to make.
    ncells : three int
        The number of cells of the stratigraphy volume and of the scalar fields.
    dem_resolution : int
        The number of DEM samples along each axis.
    line_sets : sequence of LineSet
        Lines that the caller read from the layers of the project. The bounding
        box of the model is always added when the lines are selected.
    progress : callable, optional
        Called with a text before each slow step.

    Raises
    ------
    PushError
        If there is no model, no kind is selected, or the number of cells is wrong.
    """
    model = getattr(model_manager, 'model', None)
    if model is None:
        raise PushError("There is no model to push. Build the model in step 4 first.")
    wanted = set(kinds)
    kinds = [k for k in ALL_KINDS if k in wanted]
    if not kinds:
        raise PushError("Select at least one kind of object to push.")
    ncells = tuple(int(n) for n in ncells)
    if len(ncells) != 3 or min(ncells) < 1:
        raise PushError("The number of cells must be at least 1 on each axis.")

    yield Group(ROOT_ID, 'LoopStructural model', None)
    used: set = set()
    for kind in kinds:
        label, group_id = KINDS[kind]
        if progress is not None:
            progress(f"Reading {label.lower()}...")
        yield Group(group_id, label, ROOT_ID)
        if kind in ('stratigraphy_surfaces', 'fault_surfaces'):
            items = _surface_items(model, kind, used)
        elif kind == 'stratigraphy_volume':
            items = _volume_items(model_manager, ncells, used)
        elif kind == 'scalar_fields':
            items = _scalar_field_items(model, ncells, used, progress)
        elif kind == 'dem':
            items = _dem_items(model_manager, dem_resolution, used)
        elif kind in ('points', 'vectors'):
            items = _data_items(model, kind, used)
        elif kind == 'vector_fields':
            items = _vector_field_items(model, used, progress)
        else:
            items = _line_items(model, line_sets, used)
        try:
            yield from items
        except Exception as error:
            yield Skipped(group_id, f"{label}: {error}")
