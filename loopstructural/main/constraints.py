"""The constraint types of a feature that the user builds from layers.

Each row of the constraint list of a feature is a dictionary (see
`LayerSelectionTable`). This module knows the types, the keys that each type
needs, and how to turn the points of a layer into the data frame that
LoopStructural reads. All interpolators (FDI, PLI and surfe) take the same
types. LoopStructural converts them when an interpolator needs another form.

This module does not import QGIS, so the unit tests can run it.
"""

import numpy as np
import pandas as pd

VALUE = 'Value'
INTERFACE = 'Interface'
ORIENTATION = 'Orientation'
GRADIENT_NORMAL = 'Gradient/Normal'
TANGENT = 'Tangent'
FORM_LINE = 'Form Line'
INEQUALITY = 'Inequality'
PAIRWISE_INEQUALITY = 'Pairwise Inequality'

# In the order of the type list of the user interface
CONSTRAINT_TYPES = (
    VALUE,
    INTERFACE,
    ORIENTATION,
    GRADIENT_NORMAL,
    TANGENT,
    FORM_LINE,
    INEQUALITY,
    PAIRWISE_INEQUALITY,
)

DESCRIPTIONS = {
    VALUE: "The scalar field has a known value at the points.",
    INTERFACE: "The points are on one surface. The value of the surface is not known.",
    ORIENTATION: "Strike and dip of the surface at the points.",
    GRADIENT_NORMAL: "A vector at the points, from three fields (x, y, z). A gradient has "
    "a direction and a size. A normal has a direction only.",
    TANGENT: "A vector in the surface at the points, from three fields (x, y, z).",
    FORM_LINE: "Lines on the surface. The line gives a constant value or the strike.",
    INEQUALITY: "The value at the points is above a lower limit and below an upper limit.",
    PAIRWISE_INEQUALITY: "Groups of points. The values of one group are ordered against the "
    "values of the other groups.",
}

Z_LAYER = 'layer'
Z_DEM = 'dem'
Z_CONSTANT = 'constant'
Z_SOURCES = (Z_LAYER, Z_DEM, Z_CONSTANT)
Z_LABELS = {
    Z_LAYER: "Z of the layer",
    Z_DEM: "DEM",
    Z_CONSTANT: "Constant",
}

KIND_GRADIENT = 'gradient'
KIND_NORMAL = 'normal'

DEFAULT_WEIGHT = 1.0

# The keys of a row that name a field of the layer, for each type. A row
# without these keys is not complete.
REQUIRED_FIELDS = {
    VALUE: ('value_field',),
    INTERFACE: (),
    ORIENTATION: ('strike_field', 'dip_field'),
    GRADIENT_NORMAL: ('vector_x_field', 'vector_y_field', 'vector_z_field'),
    TANGENT: ('vector_x_field', 'vector_y_field', 'vector_z_field'),
    FORM_LINE: (),
    INEQUALITY: ('lower_field', 'upper_field'),
    PAIRWISE_INEQUALITY: ('pair_field',),
}


def missing_fields(layer_data):
    """Return the keys that a row needs and does not have."""
    return [key for key in REQUIRED_FIELDS.get(layer_data.get('type'), ()) if not layer_data.get(key)]


def solver_for(layer_type):
    """Return the solver that a type needs, or None for the default.

    Inequality constraints need the ADMM solver.
    """
    return 'admm' if layer_type in (INEQUALITY, PAIRWISE_INEQUALITY) else None


def sample_layer(sampler, layer_data, dem_function, default_use_z=False):
    """Return the points of a row, with the Z that the row asks for.

    Parameters
    ----------
    sampler : callable
        Gives a data frame of points: ``sampler(df, dem_function, use_z)``.
    layer_data : dict
        The row. ``z_source`` is ``layer``, ``dem`` or ``constant``. For a
        constant, ``z_value`` is the Z. A row with no ``z_source`` (made by an
        older version) uses ``default_use_z``.
    """
    source = layer_data.get('z_source')
    use_z = default_use_z if source is None else source == Z_LAYER
    points = sampler(layer_data['df'], dem_function, use_z)
    if source == Z_CONSTANT:
        points = points.copy()
        points['Z'] = float(layer_data.get('z_value', 0.0))
    return points


def add_weight(rows, points, layer_data):
    """Add the weight of the row to ``rows``, a slice of ``points``.

    Rows that already have a weight keep it. Without a weight in the row of the
    constraint list, LoopStructural uses a weight of 1.
    """
    weight = layer_data.get('weight')
    if weight is None or 'w' in rows:
        return rows
    rows = rows.copy()
    rows['w'] = float(weight)
    return rows


def _vector_rows(points, layer_data, names):
    fields = [layer_data[key] for key in ('vector_x_field', 'vector_y_field', 'vector_z_field')]
    rows = points[['X', 'Y', 'Z']].copy()
    for name, field in zip(names, fields):
        rows[name] = pd.to_numeric(points[field], errors='coerce')
    rows = rows.dropna(subset=list(names))
    # A zero vector has no direction
    zero = (rows[list(names)] == 0).all(axis=1)
    return rows[~zero]


def interface_rows(points, layer_data, feature_name, offset=0):
    """Return the interface rows, and the offset for the next interface row.

    With a group field, the points that have the same value are on one
    surface. Without it, each feature of the layer (for example each line) is
    one surface.
    """
    field = layer_data.get('group_field')
    if field:
        codes, _ = pd.factorize(points[field])
        points = points[codes >= 0].copy()
        interface = codes[codes >= 0].astype(float)
    else:
        interface = points['feature_id'].to_numpy(float)
    count = len(np.unique(interface))
    rows = points[['X', 'Y', 'Z']].copy()
    # Different groups need different numbers, also between the rows of a feature
    _, interface = np.unique(interface, return_inverse=True)
    rows['interface'] = interface.astype(float) + offset
    rows['feature_name'] = feature_name
    return rows, offset + count


def constraint_rows(points, layer_data, feature_name):
    """Return the data frame rows of the types that this module builds.

    Types: gradient/normal, tangent, pairwise inequality. Value, orientation,
    form line and inequality are in `ModelManager._foliation_data`. Interface
    rows come from `interface_rows`.

    Returns
    -------
    pandas.DataFrame
        The rows, with the weight of the row of the constraint list.
    """
    layer_type = layer_data['type']
    if layer_type == GRADIENT_NORMAL:
        kind = layer_data.get('vector_kind', KIND_GRADIENT)
        names = ('nx', 'ny', 'nz') if kind == KIND_NORMAL else ('gx', 'gy', 'gz')
        rows = _vector_rows(points, layer_data, names)
    elif layer_type == TANGENT:
        rows = _vector_rows(points, layer_data, ('tx', 'ty', 'tz'))
    elif layer_type == PAIRWISE_INEQUALITY:
        rows = points[['X', 'Y', 'Z']].copy()
        rows['pair_id'] = pd.to_numeric(points[layer_data['pair_field']], errors='coerce')
        rows = rows.dropna(subset=['pair_id'])
    else:
        raise ValueError(f"Unknown layer type: {layer_type}")
    rows['feature_name'] = feature_name
    return add_weight(rows, points, layer_data)
