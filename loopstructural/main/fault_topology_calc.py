"""Calculate the fault topology from the fault traces.

The module has no widgets. The button in step 3 calls `calculate_fault_topology`.
The direction of a pair comes from the geometry of the traces and not from the
order of the map2loop table.
"""

from collections import namedtuple
from contextlib import nullcontext

from LoopStructural.modelling.core.fault_topology import FaultRelationshipType

TopologyResult = namedtuple('TopologyResult', ['pairs', 'undetermined'])
"""``pairs`` is the number of pairs that map2loop found.
``undetermined`` is the list of ``(fault, fault)`` pairs without a direction,
or whose relationship was set by the user and is not changed."""


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


def default_tolerance(geometry_a, geometry_b):
    """A distance that is small for the size of the two traces."""
    xmin_a, ymin_a, xmax_a, ymax_a = geometry_a.bounds
    xmin_b, ymin_b, xmax_b, ymax_b = geometry_b.bounds
    width = max(xmax_a, xmax_b) - min(xmin_a, xmin_b)
    height = max(ymax_a, ymax_b) - min(ymin_a, ymin_b)
    return max((width**2 + height**2) ** 0.5 * 1e-3, 1e-9)


def fault_pair_direction(geometry_a, geometry_b, tolerance=None):
    """Find which of two fault traces ends at the other.

    The abutting fault is the fault with an end point on the other trace.

    Parameters
    ----------
    geometry_a, geometry_b : shapely geometry
        The two traces (a line or a multi-line).
    tolerance : float, optional
        The largest distance between an end point and the other trace that
        counts as "on the trace". The default is 0.1 % of the size of the
        two traces.

    Returns
    -------
    int or None
        0 if ``geometry_a`` abuts ``geometry_b``, 1 if ``geometry_b`` abuts
        ``geometry_a``, and None if the geometry gives no direction (the
        traces cross, are separate, or end at each other).
    """
    if tolerance is None:
        tolerance = default_tolerance(geometry_a, geometry_b)
    a_abuts = any(p.distance(geometry_b) <= tolerance for p in _end_points(geometry_a))
    b_abuts = any(p.distance(geometry_a) <= tolerance for p in _end_points(geometry_b))
    if a_abuts and not b_abuts:
        return 0
    if b_abuts and not a_abuts:
        return 1
    return None


def update_topology(topology, traces, pairs, model_manager=None):
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

    Returns
    -------
    list of tuple
        The pairs that were not written: the geometry gives no direction, or
        the user already set a relationship for the pair.
    """
    skipped = []
    batch = (
        model_manager.batch_fault_topology_updates() if model_manager is not None else nullcontext()
    )
    with batch:
        # Add the faults in the order of the layer. Faults that are in the
        # topology already stay, with their relationships.
        for name in traces:
            if name not in topology.faults:
                topology.add_fault(name)
        for first, second in pairs:
            first, second = str(first), str(second)
            if first not in traces or second not in traces or first == second:
                continue
            # A relationship in either direction was set before: keep it.
            if (first, second) in topology.adjacency or (second, first) in topology.adjacency:
                skipped.append((first, second))
                continue
            direction = fault_pair_direction(traces[first], traces[second])
            if direction is None:
                skipped.append((first, second))
                continue
            abutting, other = (first, second) if direction == 0 else (second, first)
            topology.update_fault_relationship(abutting, other, FaultRelationshipType.ABUTTING)
    return skipped


def _traces_from_layer(layer, id_field):
    """Return ``(geodataframe, traces)`` from a vector layer.

    ``traces`` is a dict of the fault name to one shapely geometry, in the
    order of the layer.
    """
    import geopandas as gpd

    gdf = gpd.GeoDataFrame.from_features(layer.getFeatures())
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


def calculate_fault_topology(layer, id_field, data_manager):
    """Calculate the fault topology and write it into the data manager.

    Parameters
    ----------
    layer : QgsVectorLayer
        The fault traces.
    id_field : str
        The field with the name of the fault.
    data_manager : ModellingDataManager
        The data manager that has the fault topology.

    Returns
    -------
    TopologyResult
        The number of pairs and the pairs without a direction.

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
    skipped = update_topology(
        data_manager._fault_topology,
        traces,
        pairs,
        getattr(data_manager, '_model_manager', None),
    )
    return TopologyResult(len(pairs), skipped)


def calculate_from_data_manager(data_manager):
    """Calculate the topology with the fault layer and field of the data manager."""
    traces = data_manager.get_fault_traces() if data_manager is not None else None
    traces = traces or {}
    return calculate_fault_topology(
        traces.get('layer'), traces.get('fault_name_field'), data_manager
    )


def result_message(result):
    """Return the text for the message bar, and True if it is a warning."""
    text = f"Calculated fault topology for {result.pairs} pairs."
    if result.undetermined:
        names = ", ".join(f"{a}-{b}" for a, b in result.undetermined)
        text += (
            f" These pairs were not set (no direction from the traces, or set before): {names}."
            " Set them in the Fault Adjacency table."
        )
    return text, bool(result.undetermined)
