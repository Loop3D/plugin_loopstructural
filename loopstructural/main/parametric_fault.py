"""A fault that the user gives by numbers: a centre, a strike, a dip and a size.

Most faults come from the fault trace layer. A parametric fault has no
trace. It is one ellipsoid in space. This module makes the vectors and the
data that LoopStructural needs from the numbers of the user.

This module does not import QGIS, so the unit tests can run it.
"""

import math
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

FIELDS = (
    'name',
    'strike',
    'dip',
    'pitch',
    'displacement',
    'centre',
    'major_axis',
    'intermediate_axis',
    'minor_axis',
)


def plane_vectors(strike: float, dip: float, pitch: float) -> Tuple[np.ndarray, np.ndarray]:
    """Return the normal vector and the slip vector of a fault plane.

    Parameters
    ----------
    strike : float
        Strike in degrees clockwise from north. The plane dips to the right of
        the strike direction (right-hand rule).
    dip : float
        Dip in degrees, from 0 (flat) to 90 (vertical).
    pitch : float
        The angle of the slip in the plane, in degrees from the strike
        direction towards the down-dip direction. 0 is a strike-slip fault and
        90 is a dip-slip fault.

    Returns
    -------
    normal, slip : numpy.ndarray
        Unit vectors (x east, y north, z up). The normal points up. The slip
        vector is in the plane, so it is at right angles to the normal.
    """
    strike_r, dip_r, pitch_r = (math.radians(a) for a in (strike, dip, pitch))
    dip_direction = strike_r + math.pi / 2
    normal = np.array(
        [
            math.sin(dip_r) * math.sin(dip_direction),
            math.sin(dip_r) * math.cos(dip_direction),
            math.cos(dip_r),
        ]
    )
    along_strike = np.array([math.sin(strike_r), math.cos(strike_r), 0.0])
    down_dip = np.array(
        [
            math.cos(dip_r) * math.sin(dip_direction),
            math.cos(dip_r) * math.cos(dip_direction),
            -math.sin(dip_r),
        ]
    )
    slip = math.cos(pitch_r) * along_strike + math.sin(pitch_r) * down_dip
    return normal, slip / np.linalg.norm(slip)


def default_spec(origin: Iterable[float], maximum: Iterable[float]) -> dict:
    """Return the start values for a fault in the model area (the centre and the sizes)."""
    origin = np.asarray(list(origin), dtype=float)
    maximum = np.asarray(list(maximum), dtype=float)
    size = maximum - origin
    major = float(max(size[0], size[1]))
    return {
        'name': '',
        'strike': 0.0,
        'dip': 90.0,
        'pitch': 90.0,
        'displacement': 100.0,
        'centre': tuple(float(v) for v in (origin + maximum) / 2),
        'major_axis': major,
        'intermediate_axis': major,
        'minor_axis': major / 2,
    }


def problems(spec: dict, taken_names: Iterable[str] = ()) -> List[str]:
    """Return what is wrong with a fault, as text for the user. An empty list is a good fault."""
    found = []
    name = str(spec.get('name', '')).strip()
    if not name:
        found.append("Give the fault a name.")
    elif name in set(taken_names):
        found.append(f"The name '{name}' is already used by a feature or a fault.")
    if not 0 < float(spec.get('dip', 0)) <= 90:
        found.append("The dip must be above 0 and not more than 90 degrees.")
    for key, label in (
        ('major_axis', "The length along strike"),
        ('intermediate_axis', "The extent down dip"),
        ('minor_axis', "The influence distance"),
    ):
        if not float(spec.get(key) or 0) > 0:
            found.append(f"{label} must be more than 0.")
    centre = spec.get('centre')
    if centre is None or len(centre) != 3 or not all(math.isfinite(float(v)) for v in centre):
        found.append("The centre needs X, Y and Z.")
    return found


def frame_data(spec: dict) -> pd.DataFrame:
    """Return the data frame with the one point that LoopStructural needs.

    The point is the centre of the fault, with the value 0 of the fault
    surface. The vectors and the sizes go to LoopStructural as separate
    arguments, see `fault_arguments`.
    """
    x, y, z = (float(v) for v in spec['centre'])
    return pd.DataFrame(
        {
            'X': [x],
            'Y': [y],
            'Z': [z],
            'feature_name': [spec['name']],
            'val': [0.0],
            'coord': [0],
        }
    )


def fault_arguments(spec: dict) -> dict:
    """Return the arguments of ``GeologicalModel.create_and_add_fault`` for a fault.

    ``name`` and ``data`` are not in the result: pass the name, and
    ``frame_data(spec)`` as the data.
    """
    normal, slip = plane_vectors(spec['strike'], spec['dip'], spec.get('pitch', 90.0))
    return {
        'displacement': float(spec['displacement']),
        'fault_normal_vector': normal,
        'fault_slip_vector': slip,
        'fault_center': np.array([float(v) for v in spec['centre']]),
        'major_axis': float(spec['major_axis']),
        'intermediate_axis': float(spec['intermediate_axis']),
        'minor_axis': float(spec['minor_axis']),
        'fault_dip': float(spec['dip']),
    }


def clean_spec(spec: dict) -> dict:
    """Return the spec as plain numbers and text, safe for JSON."""
    result = {key: spec[key] for key in FIELDS if key in spec}
    result['name'] = str(result['name']).strip()
    for key in ('strike', 'dip', 'pitch', 'displacement', 'major_axis', 'intermediate_axis',
                'minor_axis'):
        if key in result:
            result[key] = float(result[key])
    result['centre'] = [float(v) for v in result['centre']]
    return result


def spec_from_dict(data: Optional[dict]) -> dict:
    """Read a spec that was saved. The centre is a tuple again."""
    spec = clean_spec(data)
    spec['centre'] = tuple(spec['centre'])
    return spec
