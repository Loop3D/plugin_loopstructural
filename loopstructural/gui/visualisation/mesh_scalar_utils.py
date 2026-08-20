"""Mesh/scalar/colormap logic factored out of ObjectPropertiesWidget.

These are the parts of that widget's behaviour that don't actually touch Qt
or the widget's own state -- they only need a mesh, a VTK mapper, or a
matplotlib Axes -- so they're pulled out here as plain functions that can be
unit tested without a QApplication or a pyvista viewer.
"""

import numpy as np


def get_scalar_values(mesh, scalar_name: str):
    """Look up a named scalar array on a pyvista-like mesh.

    `scalar_name` may be a plain point-data array name, or `cell:<name>` to
    select a cell-data array. Returns None if the mesh, name, or array is
    missing/empty.
    """
    if not scalar_name or scalar_name == "<none>" or mesh is None:
        return None
    try:
        if scalar_name.startswith('cell:'):
            name = scalar_name.split(':', 1)[1]
            cdata = getattr(mesh, 'cell_data', None) or {}
            vals = cdata.get(name, None)
        else:
            name = scalar_name
            pdata = getattr(mesh, 'point_data', None) or {}
            vals = pdata.get(name, None)
        if vals is None:
            return None
        arr = np.asarray(vals)
        if arr.size == 0:
            return None
        return arr
    except Exception:
        return None


def render_histogram(ax, values):
    """Draw a scalar histogram (or a placeholder) onto a matplotlib Axes.

    NaN/inf entries in `values` are dropped before histogramming -- passing
    them straight to `ax.hist` either raises (matplotlib cannot compute a
    finite auto-range) or silently skews the bin edges, so a message is shown
    if nothing finite remains.
    """
    ax.clear()
    finite = None
    if values is not None:
        arr = np.asarray(values, dtype=float).flatten()
        finite = arr[np.isfinite(arr)]

    if values is None or finite is None or finite.size == 0:
        message = 'No scalar selected' if values is None else 'No finite scalar values'
        ax.text(
            0.5,
            0.5,
            message,
            ha='center',
            va='center',
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        ax.hist(finite, bins=40, color='C0', alpha=0.8)
        ax.set_xlabel('Value')
        ax.set_ylabel('Count')


def stratigraphic_ids_to_rgb(ids, colours, no_data_colour=(0.6, 0.6, 0.6)):
    """Map per-point stratigraphic unit ids to an (N, 3) uint8 RGB array.

    `colours` must be indexed positionally to match
    `GeologicalModelManager.evaluate_stratigraphy_on_points`'s id scheme (see
    `GeologicalModelManager.get_stratigraphic_column_colours`). Points whose id
    falls outside `colours` (e.g. -1, meaning outside every unit) get
    `no_data_colour`.
    """
    from matplotlib.colors import to_rgb

    ids = np.asarray(ids)
    palette = np.array([to_rgb(c) for c in colours] + [to_rgb(no_data_colour)])
    no_data_index = len(colours)
    lookup = np.where((ids >= 0) & (ids < len(colours)), ids, no_data_index)
    rgb = palette[lookup]
    return (rgb * 255).astype(np.uint8)


def apply_colormap_lut(mapper, cmap, clim=None, nan_color=(0.6, 0.6, 0.6, 1.0)):
    """Build a VTK lookup table from a matplotlib colormap name and assign
    it to `mapper`, optionally scaled to `clim` (min, max).

    `nan_color` is assigned to the LUT's dedicated NaN slot (RGBA, 0..1) so
    missing/NaN scalar values render as a distinct neutral colour instead of
    silently taking on whatever colour VTK's own NaN default happens to be.
    `clim` is ignored (the LUT keeps whatever range it already had) if either
    bound is NaN/inf, since a NaN-only source array must not be allowed to
    stretch or collapse the colour range.

    Best-effort: silently does nothing if VTK/matplotlib pieces aren't
    available, or if any individual step fails -- matches the tolerance the
    rest of ObjectPropertiesWidget applies to actor/mapper manipulation,
    since mapper implementations vary across pyvista/VTK versions.
    """
    try:
        if cmap:
            vtkLookupTable = None
            try:
                from vtk import vtkLookupTable as _vtkLookupTable  # type: ignore

                vtkLookupTable = _vtkLookupTable
            except Exception:
                try:
                    from vtkmodules.vtkCommonCore import (
                        vtkLookupTable as _vtkLookupTable,  # type: ignore
                    )

                    vtkLookupTable = _vtkLookupTable
                except Exception:
                    vtkLookupTable = None
            if vtkLookupTable is not None:
                lut = vtkLookupTable()
                lut.SetNumberOfTableValues(256)
                lut.Build()
                try:
                    import matplotlib.cm as mcm

                    cm = mcm.get_cmap(cmap)
                    for i in range(256):
                        r, g, b, a = cm(i / 255.0)
                        try:
                            lut.SetTableValue(i, float(r), float(g), float(b), float(a))
                        except Exception:
                            try:
                                lut.SetTableValue(i, r, g, b, a)
                            except Exception:
                                pass
                except Exception:
                    pass

                # give NaN/missing scalar values a distinct, non-polluting colour
                try:
                    lut.SetNanColor(*nan_color)
                except Exception:
                    pass

                # set LUT range if we know clim (skip a NaN/inf clim -- that
                # would come from an all-NaN or empty source array and must
                # not be allowed to corrupt the table's range)
                try:
                    if clim is not None and len(clim) == 2:
                        lo, hi = float(clim[0]), float(clim[1])
                        if np.isfinite(lo) and np.isfinite(hi):
                            try:
                                lut.SetRange(lo, hi)
                            except Exception:
                                pass
                except Exception:
                    pass

                # assign to mapper
                try:
                    if hasattr(mapper, 'SetLookupTable'):
                        try:
                            mapper.SetLookupTable(lut)
                        except Exception:
                            pass
                    if hasattr(mapper, 'SetUseLookupTableScalarRange'):
                        try:
                            mapper.SetUseLookupTableScalarRange(True)
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass
