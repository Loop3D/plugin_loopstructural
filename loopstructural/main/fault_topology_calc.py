"""Calculate the fault topology from the fault traces.

The module has no widgets. The button in step 3 calls `calculate_fault_topology`.
The direction of a pair comes from the geometry of the traces and not from the
order of the map2loop table.
"""

import math
from collections import namedtuple
from contextlib import nullcontext

from LoopStructural.modelling.core.fault_topology import FaultRelationshipType

DEFAULT_TOLERANCE = 10.0
"""The default end-point tolerance, in map units."""

TopologyResult = namedtuple(
    'TopologyResult', ['pairs', 'undetermined', 'kept', 'warnings'], defaults=((), ())
)
"""``pairs`` is the number of pairs that map2loop found.
``undetermined`` is the list of ``(fault, fault)`` pairs without a direction.
``kept`` is the list of pairs whose relationship the user set, which are not
changed. ``warnings`` is a list of texts for the user."""

UpdateResult = namedtuple('UpdateResult', ['undetermined', 'kept'])


class FaultTopologyError(Exception):
    """The topology cannot be calculated. The text is safe to show to the user."""


def _end_points(geometry):
    """Return the end points of a trace as shapely points."""
    from shapely.ops import linemerge

    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == 'MultiLineString':
        geometry = linemerge(geometry)
    boundary = geometry.boundary
    if boundary.is_empty:  # a closed trace has no end points
        return []
    return list(boundary.geoms) if hasattr(boundary, 'geoms') else [boundary]


def fault_pair_direction(geometry_a, geometry_b, tolerance=DEFAULT_TOLERANCE):
    """Find which of two fault traces ends at the other.

    The abutting fault is the fault with an end point on the other trace.
    A trace that stops short of the other trace, or goes past it (an
    overshoot), by less than ``tolerance`` also ends at it: its end point is
    that close to the other trace. If both traces have an end point in the
    tolerance, the trace with the closer end point abuts.

    Parameters
    ----------
    geometry_a, geometry_b : shapely geometry
        The two traces (a line or a multi-line).
    tolerance : float, optional
        The largest distance, in map units, between an end point and the other
        trace that counts as "on the trace".

    Returns
    -------
    int or None
        0 if ``geometry_a`` abuts ``geometry_b``, 1 if ``geometry_b`` abuts
        ``geometry_a``, and None if the geometry gives no direction (the
        traces cross, are separate, or end at each other).
    """
    a_gap = min((p.distance(geometry_b) for p in _end_points(geometry_a)), default=math.inf)
    b_gap = min((p.distance(geometry_a) for p in _end_points(geometry_b)), default=math.inf)
    a_abuts = a_gap <= tolerance
    b_abuts = b_gap <= tolerance
    if a_abuts and b_abuts:
        if math.isclose(a_gap, b_gap, rel_tol=1e-9, abs_tol=1e-12):
            return None
        return 0 if a_gap < b_gap else 1
    if a_abuts:
        return 0
    if b_abuts:
        return 1
    return None


def unique_pairs(pairs):
    """Return the pairs as strings, without self-pairs and without a pair that
    is already in the list in either order. The first order is kept."""
    seen = set()
    result = []
    for first, second in pairs:
        first, second = str(first), str(second)
        key = frozenset((first, second))
        if first == second or key in seen:
            continue
        seen.add(key)
        result.append((first, second))
    return result


def update_topology(
    topology, traces, pairs, model_manager=None, auto_pairs=None, tolerance=DEFAULT_TOLERANCE
):
    """Write the faults and the relationships of the pairs into the topology.

    Parameters
    ----------
    topology : FaultTopology
        The topology of the modelling data manager.
    traces : dict
        Fault name to shapely geometry, in the order of the layer.
    pairs : iterable of tuple
        ``(name, name)`` pairs that are close or touch. The order is not used.
    model_manager : GeologicalModelManager, optional
        The notifications of the topology are batched when this is given.
    auto_pairs : dict, optional
        ``(abutting, other)`` to relationship, for the pairs that the last
        calculation set. This function changes it in place. A recorded pair
        that still has its relationship is removed, and set again if the
        geometry gives it. A pair that the user changed is kept.
    tolerance : float, optional
        The end-point tolerance in map units, see `fault_pair_direction`.

    Returns
    -------
    UpdateResult
        ``undetermined``: the pairs that the geometry gives no direction for.
        ``kept``: the pairs whose relationship the user set.
    """
    if auto_pairs is None:
        auto_pairs = {}
    undetermined = []
    kept = []
    batch = (
        model_manager.batch_fault_topology_updates() if model_manager is not None else nullcontext()
    )
    with batch:
        # Remove the relationships of the last calculation that the user did
        # not change, so that a changed trace does not leave an old pair.
        for pair, relationship in list(auto_pairs.items()):
            if topology.adjacency.get(pair) == relationship:
                topology.update_fault_relationship(*pair, FaultRelationshipType.NONE)
            del auto_pairs[pair]
        # Add the faults in the order of the layer. Faults that are in the
        # topology already stay, with their relationships.
        for name in traces:
            if name not in topology.faults:
                topology.add_fault(name)
        for first, second in unique_pairs(pairs):
            if first not in traces or second not in traces:
                continue
            # The user set a relationship in either direction: keep it.
            if (first, second) in topology.adjacency or (second, first) in topology.adjacency:
                kept.append((first, second))
                continue
            direction = fault_pair_direction(traces[first], traces[second], tolerance)
            if direction is None:
                undetermined.append((first, second))
                continue
            abutting, other = (first, second) if direction == 0 else (second, first)
            topology.update_fault_relationship(abutting, other, FaultRelationshipType.ABUTTING)
            auto_pairs[(abutting, other)] = FaultRelationshipType.ABUTTING
    return UpdateResult(undetermined, kept)


def _layer_crs(layer):
    """Return ``(authid, True if the units are degrees)`` of a layer, or (None, False)."""
    try:
        crs = layer.crs()
    except AttributeError:
        return None, False
    if crs is None or not crs.isValid():
        return None, False
    return crs.authid() or crs.toWkt(), bool(crs.isGeographic())


def _traces_from_layer(layer, id_field):
    """Return ``(geodataframe, traces)`` from a vector layer.

    ``traces`` is a dict of the fault name to one shapely geometry, in the
    order of the layer. The geodataframe has the CRS of the layer.
    """
    import geopandas as gpd

    crs, _degrees = _layer_crs(layer)
    gdf = gpd.GeoDataFrame.from_features(layer.getFeatures(), crs=crs)
    if gdf.empty:
        raise FaultTopologyError("The fault layer has no features.")
    if id_field not in gdf.columns:
        raise FaultTopologyError(f"The fault layer has no field '{id_field}'.")
    if id_field != "ID":
        gdf = gdf.rename(columns={id_field: "ID"})
    traces = {}
    for name, geometry in zip(gdf["ID"], gdf.geometry):
        if geometry is None or geometry.is_empty:
            continue
        name = str(name)
        if name in traces:
            traces[name] = traces[name].union(geometry)
        else:
            traces[name] = geometry
    return gdf, traces


def calculate_fault_topology(layer, id_field, data_manager, tolerance=DEFAULT_TOLERANCE):
    """Calculate the fault topology and write it into the data manager.

    Parameters
    ----------
    layer : QgsVectorLayer
        The fault traces.
    id_field : str
        The field with the name of the fault.
    data_manager : ModellingDataManager
        The data manager that has the fault topology. Its ``auto_fault_pairs``
        records the pairs that this calculation sets.
    tolerance : float, optional
        The end-point tolerance in map units, see `fault_pair_direction`.

    Returns
    -------
    TopologyResult
        The number of pairs, the pairs without a direction, the pairs of the
        user and the warnings.

    Raises
    ------
    FaultTopologyError
        If the layer or the field is missing, the layer is empty, or map2loop
        is not installed.
    """
    if layer is None:
        raise FaultTopologyError("Select a fault layer.")
    if not id_field:
        raise FaultTopologyError("Select the field with the fault name.")
    gdf, traces = _traces_from_layer(layer, id_field)
    warnings = []
    if _layer_crs(layer)[1]:
        warnings.append(
            "The fault layer uses degrees. The end-point tolerance is in the units of the "
            "layer, so use a projected CRS."
        )
    try:
        from map2loop.topology import Topology
    except ImportError as error:
        raise FaultTopologyError("Could not import the map2loop Topology class.") from error
    table = Topology(geology_data=None, fault_data=gdf).fault_fault_relationships
    pairs = []
    if table is not None and not table.empty:
        for _, row in table.iterrows():
            if 'Fault1' in row.index and 'Fault2' in row.index:
                pairs.append((row['Fault1'], row['Fault2']))
            else:
                pairs.append((row.iloc[0], row.iloc[1]))
    pairs = unique_pairs(pairs)
    if getattr(data_manager, 'auto_fault_pairs', None) is None:
        data_manager.auto_fault_pairs = {}
    result = update_topology(
        data_manager._fault_topology,
        traces,
        pairs,
        getattr(data_manager, '_model_manager', None),
        auto_pairs=data_manager.auto_fault_pairs,
        tolerance=tolerance,
    )
    return TopologyResult(len(pairs), result.undetermined, result.kept, warnings)


def calculate_from_data_manager(data_manager, tolerance=DEFAULT_TOLERANCE):
    """Calculate the topology with the fault layer and field of the data manager."""
    traces = data_manager.get_fault_traces() if data_manager is not None else None
    traces = traces or {}
    return calculate_fault_topology(
        traces.get('layer'), traces.get('fault_name_field'), data_manager, tolerance
    )


def result_message(result):
    """Return the text for the message bar, and True if it is a warning."""
    text = f"Calculated fault topology for {result.pairs} pairs."
    if result.undetermined:
        names = ", ".join(f"{a}-{b}" for a, b in result.undetermined)
        text += (
            f" The traces give no direction for these pairs: {names}."
            " Set them in the Fault Adjacency table."
        )
    if result.kept:
        names = ", ".join(f"{a}-{b}" for a, b in result.kept)
        text += f" You set these pairs, so they did not change: {names}."
    for warning in result.warnings:
        text += f" {warning}"
    return text, bool(result.undetermined or result.warnings)
