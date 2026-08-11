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
    """Draw a scalar histogram (or a placeholder) onto a matplotlib Axes."""
    ax.clear()
    if values is None:
        ax.text(
            0.5,
            0.5,
            'No scalar selected',
            ha='center',
            va='center',
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        ax.hist(values.flatten(), bins=40, color='C0', alpha=0.8)
        ax.set_xlabel('Value')
        ax.set_ylabel('Count')


def apply_colormap_lut(mapper, cmap, clim=None):
    """Build a VTK lookup table from a matplotlib colormap name and assign
    it to `mapper`, optionally scaled to `clim` (min, max).

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

                # set LUT range if we know clim
                try:
                    if clim is not None and len(clim) == 2:
                        try:
                            lut.SetRange(float(clim[0]), float(clim[1]))
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
