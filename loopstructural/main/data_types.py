"""Typed shapes for the plain-dict data structures threaded through
ModellingDataManager and GeologicalModelManager.

These are `TypedDict`s, not `dataclass`es: the values are still plain dicts
at runtime (constructed the same way, indexed with `[...]`/`.get(...)`,
unpacked with `**`, round-tripped through JSON for save/load) -- these
classes exist purely so a type checker/IDE can catch a typo'd or missing
key at the point a dict literal is built, without touching any of the
call sites that read or write them.
"""

from typing import Optional, TypedDict

import pandas as pd
from qgis.core import QgsVectorLayer


class BasalContactsConfig(TypedDict):
    """Shape of `ModellingDataManager._basal_contacts` (see `set_basal_contacts`)."""

    layer: Optional[QgsVectorLayer]
    unitname_field: Optional[str]
    use_z_coordinate: bool


class FaultTracesConfig(TypedDict):
    """Shape of `ModellingDataManager._fault_traces` (see `set_fault_traces`)."""

    layer: Optional[QgsVectorLayer]
    fault_name_field: Optional[str]
    fault_dip_field: Optional[str]
    fault_displacement_field: Optional[str]
    use_z_coordinate: bool


class StructuralOrientationsConfig(TypedDict):
    """Shape of `ModellingDataManager._structural_orientations`
    (see `set_structural_orientations`)."""

    layer: Optional[QgsVectorLayer]
    strike_field: Optional[str]
    dip_field: Optional[str]
    unitname_field: Optional[str]
    orientation_type: Optional[str]
    use_z_coordinate: bool


class FaultEntry(TypedDict, total=False):
    """Shape of a `GeologicalModelManager.faults[fault_name]` entry."""

    data: pd.DataFrame


class StratigraphyEntry(TypedDict, total=False):
    """Shape of a `GeologicalModelManager.stratigraphy[unit_name]` entry.

    `contact` and/or `orientations` may be absent depending on which kinds
    of data have been ingested for that unit.
    """

    contact: pd.DataFrame
    orientations: pd.DataFrame
