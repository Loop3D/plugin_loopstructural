"""Export of the results of a solved model to files.

The functions do not import QGIS, so the unit tests can run them. They read
the model through the model manager (`model`, `evaluate_stratigraphy_on_points`
and `get_stratigraphic_unit_names`) and write files with pyvista.
"""

import re
from pathlib import Path

import numpy as np

from loopstructural.gui.visualisation.cross_section_utils import (
    build_block_model_mesh,
    build_line_extrusion_mesh,
    build_plane_mesh,
)

# The file formats of each kind of result: extension -> label
SURFACE_FORMATS = {'.vtk': 'VTK legacy (.vtk)', '.vtp': 'VTK PolyData (.vtp)', '.ply': 'PLY (.ply)', '.stl': 'STL (.stl)'}
BLOCK_MODEL_FORMATS = {'.vtk': 'VTK legacy (.vtk)', '.vti': 'VTK ImageData (.vti)', '.csv': 'CSV (.csv)'}
CROSS_SECTION_FORMATS = {'.vtk': 'VTK legacy (.vtk)', '.csv': 'CSV (.csv)'}

STRATIGRAPHY_ID_FIELD = 'stratigraphy_id'
UNIT_FIELD = 'unit'


class ExportError(Exception):
    """The export cannot run, for example because the model is not solved."""


def safe_file_name(name: str) -> str:
    """Return ``name`` with only letters, digits, ``-``, ``_`` and ``.``."""
    cleaned = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(name)).strip('._')
    return cleaned or 'surface'


def unique_names(names):
    """Return a file-safe name for each name, with a suffix for the repeats."""
    seen = {}
    result = []
    for name in names:
        base = safe_file_name(name)
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def _require_model(model_manager):
    model = getattr(model_manager, 'model', None)
    if model is None:
        raise ExportError("There is no model to export. Build the model in step 4 first.")
    return model


def _check_extension(extension, formats):
    extension = extension.lower()
    if extension not in formats:
        raise ExportError(f"Unknown file format: {extension}")
    return extension


def unit_names_for_ids(model_manager, ids) -> np.ndarray:
    """Return the unit name for each stratigraphic id. An id of -1 has no unit."""
    names = list(model_manager.get_stratigraphic_unit_names())
    ids = np.asarray(ids, dtype=int)
    return np.array(
        [names[i] if 0 <= i < len(names) else '' for i in ids], dtype=object
    )


def add_stratigraphy(model_manager, mesh, *, cells=False):
    """Evaluate the stratigraphic column on a mesh and add the result to it.

    Adds the fields ``stratigraphy_id`` and ``unit``, to the cells or to the points.
    """
    points = mesh.cell_centers().points if cells else mesh.points
    ids = np.asarray(model_manager.evaluate_stratigraphy_on_points(points))
    data = mesh.cell_data if cells else mesh.point_data
    data[STRATIGRAPHY_ID_FIELD] = ids
    return ids


def _write_csv(path, points, ids, names):
    points = np.asarray(points)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(f"x,y,z,{STRATIGRAPHY_ID_FIELD},{UNIT_FIELD}\n")
        for (x, y, z), unit_id, name in zip(points, ids, names):
            handle.write(f"{x:.6f},{y:.6f},{z:.6f},{int(unit_id)},\"{name}\"\n")


def export_surfaces(
    model_manager,
    folder,
    extension='.vtk',
    *,
    stratigraphic=True,
    faults=True,
    progress=None,
):
    """Write one file for each surface of the model into a folder.

    Parameters
    ----------
    folder : str or Path
        The output folder. It is made if it does not exist.
    extension : str
        One of `SURFACE_FORMATS`.
    stratigraphic, faults : bool
        Which surfaces to write.
    progress : callable, optional
        Called with a message before each surface.

    Returns
    -------
    list of Path
        The files that were written. A surface with no geometry is skipped: a
        unit with no data of its own can have an isovalue that the field does
        not reach.
    """
    model = _require_model(model_manager)
    extension = _check_extension(extension, SURFACE_FORMATS)
    surfaces = []
    if stratigraphic:
        surfaces += [(f"strat_{s.name}", s) for s in model.get_stratigraphic_surfaces()]
    if faults:
        surfaces += [(f"fault_{s.name}", s) for s in model.get_fault_surfaces()]
    if not surfaces:
        raise ExportError("The model has no surfaces to export.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for file_name, (_label, surface) in zip(unique_names(l for l, _ in surfaces), surfaces):
        if progress is not None:
            progress(f"Writing {surface.name}...")
        mesh = surface.vtk()
        if mesh.n_points == 0:
            continue
        path = folder / f"{file_name}{extension}"
        mesh.save(str(path))
        written.append(path)
    if not written:
        raise ExportError("All surfaces are empty. Check the bounding box and the data.")
    return written


def export_block_model(model_manager, path, ncells, *, progress=None):
    """Write the block model: a grid that fills the bounding box.

    Each cell has the stratigraphic id and the unit name at its centre. The
    format comes from the extension of ``path`` (see `BLOCK_MODEL_FORMATS`).
    """
    model = _require_model(model_manager)
    path = Path(path)
    extension = _check_extension(path.suffix, BLOCK_MODEL_FORMATS)
    if progress is not None:
        progress("Making the block model grid...")
    mesh = build_block_model_mesh(model.bounding_box.origin, model.bounding_box.maximum, ncells)
    if progress is not None:
        progress("Evaluating the stratigraphy in the blocks...")
    ids = add_stratigraphy(model_manager, mesh, cells=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if extension == '.csv':
        _write_csv(path, mesh.cell_centers().points, ids, unit_names_for_ids(model_manager, ids))
    else:
        mesh.save(str(path))
    return path


def export_cross_section(
    model_manager,
    path,
    *,
    origin=None,
    normal=None,
    size=None,
    line_xy=None,
    resolution=100,
    z_resolution=100,
    progress=None,
):
    """Write a cross-section: a plane (``origin``, ``normal``, ``size``) or a
    vertical section under a line (``line_xy``, an (M, 2) array).
    """
    model = _require_model(model_manager)
    path = Path(path)
    extension = _check_extension(path.suffix, CROSS_SECTION_FORMATS)
    if line_xy is not None:
        bounding_box = model.bounding_box
        mesh = build_line_extrusion_mesh(
            line_xy,
            float(bounding_box.origin[2]),
            float(bounding_box.maximum[2]),
            resolution=resolution,
            z_resolution=z_resolution,
        )
    elif origin is not None and normal is not None and size:
        if np.allclose(normal, 0.0):
            raise ExportError("The normal of the cross-section cannot be the zero vector.")
        mesh = build_plane_mesh(origin, normal, size, resolution)
    else:
        raise ExportError("Give a line, or an origin, a normal and a size.")
    if progress is not None:
        progress("Evaluating the stratigraphy on the cross-section...")
    ids = add_stratigraphy(model_manager, mesh)
    path.parent.mkdir(parents=True, exist_ok=True)
    if extension == '.csv':
        _write_csv(path, mesh.points, ids, unit_names_for_ids(model_manager, ids))
    else:
        mesh.save(str(path))
    return path
