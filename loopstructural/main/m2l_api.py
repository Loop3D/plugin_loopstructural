import logging

import pandas as pd
from map2loop.contact_extractor import ContactExtractor
from map2loop.sampler import SamplerDecimator, SamplerSpacing
from map2loop.sorter import (
    SorterAgeBased,
    SorterAlpha,
    SorterMaximiseContacts,
    SorterObservationProjections,
    SorterUseNetworkX,
)
from map2loop.thickness_calculator import AlongSection, InterpolatedStructure, StructuralPoint
from qgis.core import QgsVectorLayer

from ..main.vectorLayerWrapper import qgsLayerToGeoDataFrame, qgsRasterToGdalDataset
from .debug.export import export_debug_package

logger = logging.getLogger(__name__)

# Mapping of sorter names to sorter classes
SORTER_LIST = {
    "Age based": SorterAgeBased,
    "NetworkX topological": SorterUseNetworkX,
    "Adjacency α": SorterAlpha,
    "Maximise contacts": SorterMaximiseContacts,
    "Observation projections": SorterObservationProjections,
}
PARAMETERS_DICTIONARY = {
    "Age based": SorterAgeBased.required_arguments,
    "NetworkX topological": SorterUseNetworkX.required_arguments,
    "Adjacency α": SorterAlpha.required_arguments,
    "Maximise contacts": SorterMaximiseContacts.required_arguments,
    "Observation projections": SorterObservationProjections.required_arguments,
}
# The direction of the result of these sorters (youngest or oldest first) is
# arbitrary, so it is set from the structural data after the sort (see
# orient_order_by_structure). Observation projections uses the dip, but its
# travelling salesman route loses the direction.
SORTERS_WITHOUT_YOUNGING = (
    "NetworkX topological",
    "Adjacency α",
    "Maximise contacts",
    "Observation projections",
)
# These sorters return a travelling salesman route, which is a closed cycle
# (see repair_cycle_order).
SORTERS_WITH_CYCLE = ("Maximise contacts", "Observation projections")


def repair_cycle_order(order, contacts_gdf, unitname1_column, unitname2_column):
    """Make a linear order from an order that is really a closed cycle.

    SorterMaximiseContacts solves a travelling salesman problem, which returns
    a closed route that can start at any unit, and can join two parts of the
    column at the wrong ends. So its list can start in the middle of the
    column, or have units that do not touch next to each other.

    The cycle is split at each pair of neighbours with no shared contact.
    Then the chains are joined end to end, each time with the pair of chain
    ends that has the longest shared contact (a chain is turned around if
    necessary). If there is only one chain, it is cut at the pair of
    neighbours with the shortest shared contact.
    """
    n = len(order)
    if n < 3 or contacts_gdf is None or len(contacts_gdf) == 0:
        return order
    lengths = {}
    for _, row in contacts_gdf.iterrows():
        pair = frozenset((row[unitname1_column], row[unitname2_column]))
        lengths[pair] = lengths.get(pair, 0.0) + float(row.get('length', 0.0) or 0.0)

    def contact(a, b):
        return lengths.get(frozenset((a, b)), 0.0)

    weights = [contact(order[i], order[(i + 1) % n]) for i in range(n)]
    # rotate so that the list starts after the weakest link
    weakest = n - 1 if weights[-1] <= min(weights) else weights.index(min(weights))
    order = order[weakest + 1 :] + order[: weakest + 1]
    if min(weights) > 0:
        return order

    # split into chains at the links with no contact
    chains = [[order[0]]]
    for previous, unit in zip(order, order[1:]):
        if contact(previous, unit) > 0:
            chains[-1].append(unit)
        else:
            chains.append([unit])
    if len(chains) == 1:
        return order

    # join the chains, starting with the longest one
    chains.sort(key=len, reverse=True)
    result = chains.pop(0)
    while chains:
        best = None
        for i, chain in enumerate(chains):
            for candidate in (chain, chain[::-1]):
                # candidate after result, or candidate before result
                for at_end, value in (
                    (True, contact(result[-1], candidate[0])),
                    (False, contact(candidate[-1], result[0])),
                ):
                    if best is None or value > best[0]:
                        best = (value, i, candidate, at_end)
        _, i, candidate, at_end = best
        chains.pop(i)
        result = result + candidate if at_end else candidate + result
    return result


def orient_order_by_structure(
    order, geology_gdf, unit_name_field, structure_gdf, max_distance=2000.0
):
    """Count the structural measurements that agree with a youngest-first order.

    For each measurement, find the unit that contains it and the first other
    unit along a line in the dip direction. For upright beds that unit is
    younger, so it must come before the containing unit in `order`.

    Parameters
    ----------
    order : list
        Unit names, youngest first.
    geology_gdf : GeoDataFrame
        Geology polygons.
    unit_name_field : str
        Name of the unit name column in `geology_gdf`.
    structure_gdf : GeoDataFrame
        Point measurements with 'DIP' and 'DIPDIR' columns in degrees.
    max_distance : float, optional
        Length of the line in the dip direction, in map units.

    Returns
    -------
    tuple(int, int)
        (measurements that agree with `order`, measurements that do not)
    """
    import math

    from shapely.geometry import LineString

    index = {name: i for i, name in enumerate(order)}
    geology = geology_gdf[[unit_name_field, 'geometry']].reset_index(drop=True)
    sindex = geology.sindex
    agree = 0
    disagree = 0
    for _, row in structure_gdf.iterrows():
        point = row.geometry
        dip = row.get('DIP')
        dipdir = row.get('DIPDIR')
        if point is None or point.geom_type != 'Point' or pd.isna(dip) or pd.isna(dipdir):
            continue
        if float(dip) <= 0:
            # a horizontal bed has no dip direction
            continue
        containing = geology.iloc[sindex.query(point, predicate='within')]
        if containing.empty:
            continue
        unit_a = containing.iloc[0][unit_name_field]
        angle = math.radians(float(dipdir))
        end = (
            point.x + math.sin(angle) * max_distance,
            point.y + math.cos(angle) * max_distance,
        )
        line = LineString([(point.x, point.y), end])
        candidates = geology.iloc[sindex.query(line, predicate='intersects')]
        candidates = candidates[candidates[unit_name_field] != unit_a]
        if candidates.empty:
            continue
        distances = [point.distance(line.intersection(g)) for g in candidates.geometry]
        unit_b = candidates.iloc[int(min(range(len(distances)), key=distances.__getitem__))][
            unit_name_field
        ]
        if unit_a not in index or unit_b not in index:
            continue
        if index[unit_b] < index[unit_a]:
            agree += 1
        else:
            disagree += 1
    return agree, disagree


def extract_basal_contacts(
    geology,
    stratigraphic_order,
    faults=None,
    ignore_units=[],
    unit_name_field=None,
    all_contacts=False,
    updater=None,
    debug_manager=None,
    target_crs=None,
    unit_colours=None,
):
    """Extract basal contacts from geological data.

    Parameters
    ----------
    geology : QgsVectorLayer or GeoDataFrame
        Geological layer as a GeoDataFrame or QgsVectorLayer.
    stratigraphic_order : list
        List defining the stratigraphic order of units.
    faults : QgsVectorLayer or GeoDataFrame, optional
        Faults layer as a GeoDataFrame or QgsVectorLayer, by default None.
    ignore_units : list, optional
        List of unit names to ignore, by default None.
    unit_name_field : str, optional
        Name of the field containing unit names, by default None.
    all_contacts : bool, optional
        Whether to return all contacts in addition to basal contacts, by default False.
    updater : callable, optional
        Callback function for progress updates, by default None.
    target_crs : QgsCoordinateReferenceSystem, optional
        CRS to reproject both geology and faults into before extraction, so
        the two layers line up spatially. If None, geology and faults keep
        their own source CRS, which silently produces wrong (often empty)
        results whenever the two layers were digitised in different CRSs.
    unit_colours : dict, optional
        Mapping of unit name to colour. When given, a 'colour' column is
        added to the returned basal contacts, looked up by the 'basal_unit'
        each contact was extracted for.

    Returns
    -------
    dict
        Dictionary containing 'basal_contacts' GeoDataFrame and optionally 'all_contacts' GeoDataFrame.
    """
    geology = qgsLayerToGeoDataFrame(geology, target_crs=target_crs)
    if unit_name_field and unit_name_field in geology.columns:
        mask = ~geology[unit_name_field].astype(str).str.strip().isin(ignore_units or [])
        geology = geology[mask].reset_index(drop=True)
        if updater:
            updater(f"filtered by unit name field: {unit_name_field}")
    else:
        if updater:
            updater(f"no unit name field found: {unit_name_field}")

    faults = qgsLayerToGeoDataFrame(faults, target_crs=target_crs) if faults else None
    if unit_name_field and unit_name_field != 'UNITNAME' and unit_name_field in geology.columns:
        # Drop any pre-existing 'UNITNAME' column first -- otherwise the rename
        # below leaves two columns named 'UNITNAME', which breaks any later
        # column selection on 'UNITNAME' (it returns a DataFrame, not a Series).
        if 'UNITNAME' in geology.columns:
            geology = geology.drop(columns=['UNITNAME'])
        geology = geology.rename(columns={unit_name_field: 'UNITNAME'})
    # Log parameters via DebugManager if provided
    ignore_units += [None]

    # Units in the geology layer that are not in the stratigraphic column are
    # kept in the geology (so they still bound the other units and appear in
    # all contacts), but contacts that touch them are left out of the basal
    # contacts. Tell the user which units are skipped.
    unit_name_col = 'UNITNAME' if 'UNITNAME' in geology.columns else unit_name_field
    if unit_name_col and unit_name_col in geology.columns:
        geology_unit_names = {str(v).strip() for v in geology[unit_name_col].dropna().unique()}
        stratigraphic_names = {
            str(name).strip() for name in stratigraphic_order if name is not None
        }
        ignored_names = {str(unit).strip() for unit in ignore_units if unit is not None}
        missing_from_column = sorted(geology_unit_names - stratigraphic_names - ignored_names)
        if missing_from_column:
            message = (
                "The geology layer has unit(s) with no entry in the stratigraphic column: "
                + ", ".join(repr(name) for name in missing_from_column)
                + ". Contacts with these unit(s) are not included in the basal contacts."
            )
            logger.warning(message)
            if updater:
                updater(message)

    if debug_manager:
        debug_manager.log_params(
            "extract_basal_contacts",
            {
                "stratigraphic_order": stratigraphic_order,
                "ignore_units": ignore_units,
                "unit_name_field": unit_name_field,
                "all_contacts": all_contacts,
                "geology": geology,
                "faults": faults,
            },
        )
    if updater:
        updater("Extracting Basal Contacts...")
    contact_extractor = ContactExtractor(geology, faults)
    # If debug_manager present and debug mode enabled, export tool, layers and params
    try:
        if debug_manager and getattr(debug_manager, "is_debug", lambda: False)():

            _layers = {"geology": geology, "faults": faults}
            _pickles = {"contact_extractor": contact_extractor}
            # export layers and pickles first to get the actual filenames used
            _exported = export_debug_package(
                debug_manager,
                runner_script_name="run_extract_basal_contacts.py",
                m2l_object=contact_extractor,
                params={'stratigraphic_order': stratigraphic_order},
            )

    except Exception:
        logger.exception("Failed to save basal-contacts debug info")

    try:
        all_contacts_result = contact_extractor.extract_all_contacts()
        # map2loop raises if a contact has a unit that is not in the column,
        # so give it only the contacts between units that are in the column.
        column_units = [name for name in stratigraphic_order if name is not None]
        contact_extractor.contacts = all_contacts_result[
            all_contacts_result['UNITNAME_1'].isin(column_units)
            & all_contacts_result['UNITNAME_2'].isin(column_units)
        ].reset_index(drop=True)
        basal_contacts = contact_extractor.extract_basal_contacts(column_units)
        logger.debug(
            "Extracted contacts: all=%s basal=%s",
            all_contacts_result.shape,
            basal_contacts.shape,
        )
    except Exception:
        logger.exception("Error during contact extraction")
        basal_contacts = pd.DataFrame()
        all_contacts_result = pd.DataFrame()

    if ignore_units and basal_contacts.empty is False:
        basal_contacts = basal_contacts[
            ~basal_contacts['basal_unit'].astype(str).str.strip().isin(ignore_units)
        ].reset_index(drop=True)
    if unit_colours and basal_contacts.empty is False and 'basal_unit' in basal_contacts.columns:
        colours_by_name = {str(name).strip(): colour for name, colour in unit_colours.items()}
        basal_contacts['colour'] = basal_contacts['basal_unit'].astype(str).str.strip().map(
            colours_by_name
        )
    if all_contacts:
        return {'basal_contacts': basal_contacts, 'all_contacts': all_contacts_result}
    return {'basal_contacts': basal_contacts}


def _extract_contacts_for_sorting(geology_gdf, unit_name_field, updater=None):
    """Derive unit-to-unit contacts directly from geology, for sorters that need adjacency.

    SorterAlpha, SorterMaximiseContacts and SorterObservationProjections all
    require a 'contacts' GeoDataFrame with 'UNITNAME_1'/'UNITNAME_2' columns.
    Unlike basal contacts, this adjacency doesn't depend on a stratigraphic
    order -- which isn't known yet at this point, since sorting is what
    produces it -- so it can always be derived from the geology layer alone.
    """
    geology_gdf = geology_gdf.copy()
    if unit_name_field and unit_name_field != 'UNITNAME' and unit_name_field in geology_gdf.columns:
        # Drop any pre-existing 'UNITNAME' column first -- otherwise the rename
        # below leaves two columns named 'UNITNAME', and geology_gdf["UNITNAME"]
        # returns a DataFrame instead of a Series, which crashes dissolve()
        # inside extract_all_contacts with "Grouper for 'UNITNAME' not
        # 1-dimensional".
        if 'UNITNAME' in geology_gdf.columns:
            geology_gdf = geology_gdf.drop(columns=['UNITNAME'])
        geology_gdf = geology_gdf.rename(columns={unit_name_field: 'UNITNAME'})
    if updater:
        updater("Extracting contacts from geology...")
    return ContactExtractor(geology_gdf, None).extract_all_contacts()


def sort_stratigraphic_column(
    geology,
    sorting_algorithm="Observation projections",
    unit_name_field="UNITNAME",
    min_age_field=None,
    max_age_field=None,
    unitname1_field=None,
    unitname2_field=None,
    structure=None,
    dip_field="DIP",
    dipdir_field="DIPDIR",
    orientation_type="Dip Direction",
    dtm=None,
    debug_manager=None,
    updater=None,
    contacts=None,
):
    """Sort stratigraphic units using map2loop sorters.

    Parameters
    ----------
    geology : QgsVectorLayer or GeoDataFrame
        Geology polygon layer.
    contacts : QgsVectorLayer or GeoDataFrame, optional
        Contacts line layer. Only needed to override the contacts that are
        otherwise extracted automatically from `geology` for sorting
        algorithms that need adjacency information (Adjacency α, Maximise
        contacts, Observation projections).
    sorting_algorithm : str, optional
        Name of the sorting algorithm, by default "Observation projections".
    unit_name_field : str, optional
        Name of the unit name field, by default "UNITNAME".
    min_age_field : str, optional
        Name of the minimum age field, by default None.
    max_age_field : str, optional
        Name of the maximum age field, by default None.
    group_field : str, optional
        Name of the group field, by default None.
    structure : QgsVectorLayer or GeoDataFrame, optional
        Structure point layer, by default None.
    dip_field : str, optional
        Name of the dip field, by default "DIP".
    dipdir_field : str, optional
        Name of the dip direction field, by default "DIPDIR".
    orientation_type : str, optional
        Type of orientation ("Dip Direction" or "Strike"), by default "Dip Direction".
    dtm : QgsRasterLayer or GDAL dataset, optional
        Digital terrain model, by default None.
    updater : callable, optional
        Callback function for progress updates, by default None.

    Returns
    -------
    list
        List of unit names sorted from youngest to oldest.
    """
    if updater:
        updater(f"Sorting using {sorting_algorithm}...")

    # Get the sorter class
    sorter_cls = SORTER_LIST.get(sorting_algorithm, SorterObservationProjections)
    required_args = getattr(sorter_cls, 'required_arguments', [])

    # Convert layers to GeoDataFrames
    geology_gdf = qgsLayerToGeoDataFrame(geology)
    if contacts is not None:
        contacts_gdf = qgsLayerToGeoDataFrame(contacts)
    elif 'contacts' in required_args or 'relationships' in required_args:
        contacts_gdf = _extract_contacts_for_sorting(geology_gdf, unit_name_field, updater)
    else:
        contacts_gdf = pd.DataFrame()

    # Log parameters via DebugManager if provided
    if debug_manager:
        debug_manager.log_params(
            "sort_stratigraphic_column",
            {
                "sorting_algorithm": sorting_algorithm,
                "unit_name_field": unit_name_field,
                "min_age_field": min_age_field,
                "max_age_field": max_age_field,
                "orientation_type": orientation_type,
                "dtm": dtm,
                "geology": geology_gdf,
                "contacts": contacts_gdf,
            },
        )

    # Build units DataFrame
    if (
        unit_name_field
        and unit_name_field != unit_name_field
        and unit_name_field in geology_gdf.columns
    ):
        units_df = geology_gdf[[unit_name_field]].drop_duplicates().reset_index(drop=True)
        units_df = units_df.rename(columns={unit_name_field: unit_name_field})

    elif unit_name_field in geology_gdf.columns:
        units_df = geology_gdf[[unit_name_field]].drop_duplicates().reset_index(drop=True)
    else:
        raise ValueError(f"Unit name field '{unit_name_field}' not found in geology data")
    if min_age_field and min_age_field in geology_gdf.columns:
        units_df = units_df.merge(
            geology_gdf[[unit_name_field, min_age_field]].drop_duplicates(),
            on=unit_name_field,
            how='left',
        )
    if max_age_field and max_age_field in geology_gdf.columns:
        units_df = units_df.merge(
            geology_gdf[[unit_name_field, max_age_field]].drop_duplicates(),
            on=unit_name_field,
            how='left',
        )
    # SorterUseNetworkX reads the literal 'layerId' and 'name' columns, and
    # looks up units["name"][layerId], so layerId must be the row index.
    units_df = units_df.reset_index(drop=True)
    units_df['layerId'] = units_df.index
    if 'name' not in units_df.columns:
        units_df['name'] = units_df[unit_name_field]
    # Build relationships DataFrame (contacts without geometry)
    relationships_df = contacts_gdf.copy()
    if 'geometry' in relationships_df.columns:
        relationships_df = relationships_df.drop(columns=['geometry'])
    if 'length' in relationships_df.columns:
        relationships_df = relationships_df.drop(columns=['length'])

    # Convert structure layer to a GeoDataFrame with 'DIP'/'DIPDIR' columns,
    # matching the hardcoded column names map2loop's sorters read.
    structure_gdf = None
    if structure is not None:
        if dip_field and dipdir_field and dip_field == dipdir_field:
            raise ValueError(
                f"The dip field and the dip direction/strike field are both '{dip_field}'. "
                "Select a different field for each."
            )
        structure_gdf = qgsLayerToGeoDataFrame(structure)
        # Copy the columns (do not rename them), so that one source column
        # can not remove the other one.
        dip_values = None
        if dip_field and dip_field in structure_gdf.columns:
            dip_values = structure_gdf[dip_field].copy()
        if dipdir_field and dipdir_field in structure_gdf.columns:
            if orientation_type == 'Strike':
                structure_gdf['DIPDIR'] = structure_gdf[dipdir_field].apply(
                    lambda val: (val + 90.0) % 360.0 if pd.notna(val) else val
                )
            elif orientation_type == 'Dip Direction':
                structure_gdf['DIPDIR'] = structure_gdf[dipdir_field]
        if dip_values is not None:
            structure_gdf['DIP'] = dip_values

    # Convert DTM to a GDAL dataset, as map2loop's sorters read it via GDAL calls.
    dtm_gdal = None
    if dtm is not None:
        if hasattr(dtm, 'source'):  # It's a QgsRasterLayer
            dtm_gdal = qgsRasterToGdalDataset(dtm)
        else:
            dtm_gdal = dtm

    # Prepare all possible arguments
    all_args = {
        'geology_data': geology_gdf,
        'contacts': contacts_gdf,
        'relationships': relationships_df,
        'unit_name_field': unit_name_field,
        'min_age_column': min_age_field,
        'max_age_column': max_age_field,
        'structure_data': structure_gdf,
        'dip_field': dip_field,
        'dipdir_field': dipdir_field,
        'orientation_type': orientation_type,
        'dtm_data': dtm_gdal,
        'updater': updater,
        'unit_name_column': unit_name_field,
    }
    # Only override the sorter's own 'UNITNAME_1'/'UNITNAME_2' defaults when the
    # caller explicitly names different columns -- passing None here would
    # clobber those defaults and break the lookup against the extracted contacts.
    if unitname1_field:
        all_args['unitname1_column'] = unitname1_field
    if unitname2_field:
        all_args['unitname2_column'] = unitname2_field

    # Only pass required arguments to the sorter
    sorter_args = {k: v for k, v in all_args.items() if k in required_args}
    logger.debug('Calling sorter with args: %s', list(sorter_args.keys()))
    sorter = sorter_cls(**sorter_args)
    # If debugging, pickle sorter and write a small runner script
    try:
        if debug_manager and getattr(debug_manager, "is_debug", lambda: False)():

            _exported = export_debug_package(
                debug_manager,
                m2l_object=sorter,
                params={'units_df': units_df},
                runner_script_name="run_sort_stratigraphic_column.py",
            )

    except Exception:
        logger.exception("Failed to save sorter debug info")

    order = sorter.sort(units_df)
    if updater:
        updater(f"Sorting complete: {len(order)} units ordered")

    if sorting_algorithm in SORTERS_WITH_CYCLE:
        order = repair_cycle_order(
            order,
            contacts_gdf,
            all_args.get('unitname1_column', 'UNITNAME_1'),
            all_args.get('unitname2_column', 'UNITNAME_2'),
        )

    if sorting_algorithm in SORTERS_WITHOUT_YOUNGING:
        if (
            structure_gdf is not None
            and 'DIP' in structure_gdf.columns
            and 'DIPDIR' in structure_gdf.columns
        ):
            agree, disagree = orient_order_by_structure(
                order, geology_gdf, unit_name_field, structure_gdf
            )
            if disagree > agree:
                order = list(reversed(order))
            message = (
                f"Younging direction from structural data: {max(agree, disagree)} of "
                f"{agree + disagree} measurements agree"
                + (" (order reversed)." if disagree > agree else ".")
            )
        else:
            message = (
                f"{sorting_algorithm} does not find which unit is youngest. Select a "
                "structure layer to set the direction, or examine the column."
            )
        logger.info(message)
        if updater:
            updater(message)

    return order


def sample_contacts(
    spatial_data,
    sampler_type="Spacing",
    decimation=None,
    spacing=None,
    dtm=None,
    geology=None,
    debug_manager=None,
    updater=None,
):
    """Sample spatial data using map2loop samplers.

    Parameters
    ----------
    spatial_data : QgsVectorLayer or GeoDataFrame
        Spatial data to sample (points or lines).
    sampler_type : str, optional
        Type of sampler ("Decimator" or "Spacing"), by default "Spacing".
    decimation : int, optional
        Decimation factor for Decimator, by default None.
    spacing : float, optional
        Spacing for Spacing sampler, by default None.
    dtm : QgsRasterLayer or GDAL dataset, optional
        Digital terrain model, by default None.
    geology : QgsVectorLayer or GeoDataFrame, optional
        Geology polygon layer, by default None.
    updater : callable, optional
        Callback function for progress updates, by default None.

    Returns
    -------
    GeoDataFrame
        Sampled data as GeoDataFrame.
    """
    if updater:
        updater(f"Sampling using {sampler_type}...")

    # Convert spatial data to GeoDataFrame
    spatial_gdf = qgsLayerToGeoDataFrame(spatial_data)

    # Convert DTM to GDAL dataset if needed
    dtm_gdal = None
    if dtm is not None:
        if hasattr(dtm, 'source'):  # It's a QgsRasterLayer
            dtm_gdal = qgsRasterToGdalDataset(dtm)
        else:
            dtm_gdal = dtm

    # Convert geology to GeoDataFrame if provided
    geology_gdf = None
    if geology is not None:
        geology_gdf = qgsLayerToGeoDataFrame(geology)

    # Log parameters via DebugManager if provided
    if debug_manager:
        debug_manager.log_params(
            "sample_contacts",
            {
                "sampler_type": sampler_type,
                "decimation": decimation,
                "spacing": spacing,
                "dtm": dtm,
                "geology": geology_gdf,
                "spatial_data": spatial_gdf,
            },
        )

    # Run sampler
    if sampler_type == "Decimator":
        if decimation is None:
            raise ValueError("decimation parameter is required for Decimator sampler")
        sampler = SamplerDecimator(
            decimation=decimation, dtm_data=dtm_gdal, geology_data=geology_gdf
        )
    else:  # Spacing
        if spacing is None:
            raise ValueError("spacing parameter is required for Spacing sampler")
        sampler = SamplerSpacing(spacing=spacing, dtm_data=dtm_gdal, geology_data=geology_gdf)

    samples = sampler.sample(spatial_gdf)

    try:
        if debug_manager and getattr(debug_manager, "is_debug", lambda: False)():
            _exported = export_debug_package(
                debug_manager,
                m2l_object=sampler,
                params={'spatial_data': spatial_gdf},
                runner_script_name='run_sample_contacts.py',
            )

    except Exception:
        logger.exception("Failed to save sampler debug info")

    return samples


def calculate_thickness(
    geology,
    structure,
    sampling_frequency,
    basal_contacts=None,
    cross_sections=None,
    calculator_type="InterpolatedStructure",
    dtm=None,
    unit_name_field="UNITNAME",
    dip_field="DIP",
    dipdir_field="DIPDIR",
    orientation_type="Dip Direction",
    max_line_length=None,
    stratigraphic_order=None,
    debug_manager=None,
    updater=None,
    basal_contacts_unit_name=None,
):
    """Calculate thickness using map2loop thickness calculators.

    Parameters
    ----------
    geology : QgsVectorLayer or GeoDataFrame
        Geology polygon layer.
    basal_contacts : QgsVectorLayer or GeoDataFrame, optional
        Basal contacts line layer, by default None. If not supplied, basal
        contacts are calculated automatically from `geology` and
        `stratigraphic_order` (which must then be provided).
    structure : QgsVectorLayer or GeoDataFrame
        Structure point layer with orientation data.
    sampling_frequency : float
        Spacing at which to sample points along the basal contacts, used to
        build the sampled contacts points required by the thickness
        calculators.
    cross_sections : QgsVectorLayer or GeoDataFrame, optional
        Cross-sections line layer, by default None.
    calculator_type : str, optional
        Type of calculator ("InterpolatedStructure" or "StructuralPoint"), by default "InterpolatedStructure".
    dtm : QgsRasterLayer or GDAL dataset, optional
        Digital terrain model, by default None.
    unit_name_field : str, optional
        Name of the unit name field, by default "UNITNAME".
    dip_field : str, optional
        Name of the dip field, by default "DIP".
    dipdir_field : str, optional
        Name of the dip direction field, by default "DIPDIR".
    orientation_type : str, optional
        Type of orientation ("Dip Direction" or "Strike"), by default "Dip Direction".
    max_line_length : float, optional
        Maximum line length for StructuralPoint calculator, by default None.
    stratigraphic_order : list, optional
        List of unit names in stratigraphic order, by default None.
    updater : callable, optional
        Callback function for progress updates, by default None.

    Returns
    -------
    GeoDataFrame
        Calculated thickness data as GeoDataFrame.
    """
    if updater:
        updater(f"Calculating thickness using {calculator_type}...")

    # Convert layers to GeoDataFrames
    geology_gdf = qgsLayerToGeoDataFrame(geology)
    basal_contacts_gdf = None
    if basal_contacts is not None:
        basal_contacts_gdf = qgsLayerToGeoDataFrame(basal_contacts)
        basal_contacts_gdf = (
            basal_contacts_gdf.rename(columns={basal_contacts_unit_name: 'basal_unit'})
            if basal_contacts_unit_name
            else basal_contacts_gdf
        )
        # A memory layer has no features after the project is opened again,
        # so treat an empty layer the same as no layer.
        if basal_contacts_gdf is None or basal_contacts_gdf.empty:
            if not stratigraphic_order:
                raise ValueError(
                    "The basal contacts layer has no features. Run the basal contacts "
                    "extractor again, or define the stratigraphic column so basal "
                    "contacts can be calculated from the geology layer."
                )
            if updater:
                updater("The basal contacts layer has no features; calculating them from geology...")
            basal_contacts_gdf = None
    if basal_contacts_gdf is None:
        # No basal contacts layer supplied -- derive it from the geology
        # layer and the stratigraphic order instead of failing.
        if not stratigraphic_order:
            raise ValueError(
                "No basal contacts layer was supplied and no stratigraphic order is "
                "available to calculate it automatically. Either select a basal "
                "contacts layer, or define the stratigraphic column so basal "
                "contacts can be derived from the geology layer."
            )
        if updater and basal_contacts is None:
            updater("No basal contacts layer supplied; calculating basal contacts from geology...")
        basal_contacts_gdf = extract_basal_contacts(
            geology=geology,
            stratigraphic_order=stratigraphic_order,
            unit_name_field=unit_name_field,
            updater=updater,
            debug_manager=debug_manager,
            target_crs=geology.crs() if hasattr(geology, 'crs') else None,
        )['basal_contacts']
    structure_gdf = qgsLayerToGeoDataFrame(structure)
    cross_sections_gdf = qgsLayerToGeoDataFrame(cross_sections)

    # Convert DTM to GDAL dataset if needed (used below for sampling, and
    # again for the thickness calculator itself).
    dtm_gdal = None
    if dtm is not None:
        if hasattr(dtm, 'source'):  # It's a QgsRasterLayer
            dtm_gdal = qgsRasterToGdalDataset(dtm)
        else:
            dtm_gdal = dtm

    if updater:
        updater(f"Sampling basal contacts at spacing {sampling_frequency}...")
    sampler = SamplerSpacing(spacing=sampling_frequency, dtm_data=dtm_gdal, geology_data=geology_gdf)
    sampled_contacts_gdf = sampler.sample(basal_contacts_gdf)
    if sampled_contacts_gdf is None or len(sampled_contacts_gdf) == 0:
        raise ValueError(
            "No points were sampled along the basal contacts. Check that the basal "
            "contacts layer has features and that the sampling frequency is smaller "
            "than the contact lengths."
        )

    # Log parameters via DebugManager if provided
    if debug_manager:
        debug_manager.log_params(
            "calculate_thickness",
            {
                "calculator_type": calculator_type,
                "unit_name_field": unit_name_field,
                "orientation_type": orientation_type,
                "max_line_length": max_line_length,
                "stratigraphic_order": stratigraphic_order,
                "geology": geology_gdf,
                "basal_contacts": basal_contacts_gdf,
                "sampled_contacts": sampled_contacts_gdf,
                "structure": structure_gdf,
                "cross_sections": cross_sections_gdf,
            },
        )

    bounding_box = {
        'maxx': geology_gdf.total_bounds[2],
        'minx': geology_gdf.total_bounds[0],
        'maxy': geology_gdf.total_bounds[3],
        'miny': geology_gdf.total_bounds[1],
    }

    # Rename unit name field if needed
    if unit_name_field and unit_name_field != 'UNITNAME':
        if unit_name_field in geology_gdf.columns:
            geology_gdf = geology_gdf.rename(columns={unit_name_field: 'UNITNAME'})

    if dip_field and dipdir_field and dip_field == dipdir_field:
        raise ValueError(
            f"The dip field and the dip direction/strike field are both '{dip_field}'. "
            "Select a different field for each."
        )
    # Copy the columns (do not rename them), so that one source column can
    # not remove the other one.
    dip_values = None
    if dip_field and dip_field in structure_gdf.columns:
        dip_values = structure_gdf[dip_field].copy()

    # Handle dip direction field based on orientation type
    if dipdir_field and dipdir_field in structure_gdf.columns:
        if orientation_type == 'Strike':
            structure_gdf['DIPDIR'] = structure_gdf[dipdir_field].apply(
                lambda val: (val + 90.0) % 360.0 if pd.notna(val) else val
            )
        elif orientation_type == 'Dip Direction':
            structure_gdf['DIPDIR'] = structure_gdf[dipdir_field]
    if dip_values is not None:
        structure_gdf['DIP'] = dip_values

    # Run thickness calculator
    if calculator_type == "InterpolatedStructure":
        calculator = InterpolatedStructure(
            bounding_box=bounding_box,
            dtm_data=dtm_gdal,
            is_strike=orientation_type == 'Strike',
            max_line_length=max_line_length,
        )
    if calculator_type == "StructuralPoint":
        if max_line_length is None:
            raise ValueError("max_line_length parameter is required for StructuralPoint calculator")
        calculator = StructuralPoint(
            bounding_box=bounding_box,
            dtm_data=dtm_gdal,
            is_strike=orientation_type == 'Strike',
            max_line_length=max_line_length,
        )
    if calculator_type == "AlongSection":
        calculator = AlongSection(
            bounding_box=bounding_box,
            sections=cross_sections_gdf,
        )

    if unit_name_field != 'UNITNAME' and unit_name_field in geology_gdf.columns:
        geology_gdf = geology_gdf.rename(columns={unit_name_field: 'UNITNAME'})
    units = geology_gdf.copy()

    units_unique = units.drop_duplicates(subset=['UNITNAME']).reset_index(drop=True)
    units = pd.DataFrame({'name': units_unique['UNITNAME']})
    basal_contacts_gdf['type'] = 'BASAL'  # required by calculator
    structure_gdf['X'] = structure_gdf.geometry.x
    structure_gdf['Y'] = structure_gdf.geometry.y
    # No local export path placeholders required; export_debug_package handles exports
    try:
        if debug_manager and getattr(debug_manager, "is_debug", lambda: False)():
            # Export layers and pickled objects first to get their exported filenames
            _exported = export_debug_package(
                debug_manager,
                runner_script_name="run_calculate_thickness.py",
                m2l_object=calculator,
                params={
                    'units': units,
                    'stratigraphic_order': stratigraphic_order,
                    'basal_contacts': basal_contacts_gdf,
                    'structure_data': structure_gdf,
                    'geology_data': geology_gdf,
                    'sampled_contacts': sampled_contacts_gdf,
                },
            )

    except Exception:
        logger.exception("Failed to save thickness-calculator debug info")
        raise

    thickness = calculator.compute(
        units,
        stratigraphic_order,
        basal_contacts_gdf,
        structure_gdf,
        geology_gdf,
        sampled_contacts_gdf,
    )
    # Ensure result object exists for return and for any debug export
    res = {'thicknesses': thickness}
    return res


def paint_stratigraphic_order(
    geology_layer: 'QgsVectorLayer',
    stratigraphic_order: list,
    unit_name_field: str = "UNITNAME",
    debug_manager=None,
    updater=None,
):
    """Paint stratigraphic order onto geology polygons.
    Parameters
    ----------
    geology_layer : QgsVectorLayer
        Geology polygon layer.
    stratigraphic_order : list
        List of unit names in stratigraphic order.
    unit_name_field : str
        Name of the field containing unit names.
    debug_manager : DebugManager
        Debug manager instance for handling debug information.
    updater : Updater
        Updater instance for handling updates.
    Returns
    -------
    None
    """
    if updater:
        updater("Painting stratigraphic order...")
    # check unit_name_field exists in geology_layer
    # Use the QGIS layer directly (if provided), otherwise accept a GeoDataFrame
    if geology_layer is None:
        msg = "No geology layer provided"
        if debug_manager:
            try:
                debug_manager.log_params("paint_stratigraphic_order", {"error": msg})
            except Exception:
                pass
        if updater:
            updater(msg)
        raise ValueError(msg)

    geology_fields = None
    # Try to treat as a QgsVectorLayer
    if issubclass(type(geology_layer), QgsVectorLayer):
        fields = geology_layer.fields()
        if fields is not None:
            try:
                # QgsFields has .names() in many QGIS versions
                geology_fields = list(fields.names())
            except Exception:
                # Fallback: iterate field objects
                geology_fields = [f.name() for f in fields]
            finally:
                pass
        if unit_name_field not in geology_fields:
            msg = f"Unit name field '{unit_name_field}' not found in geology layer"
            if debug_manager:
                try:
                    debug_manager.log_params(
                        "paint_stratigraphic_order",
                        {"error": msg, "geology_fields": geology_fields},
                    )
                except Exception:
                    pass
            if updater:
                updater(msg)
            raise ValueError(msg)
        if updater:
            updater(f"Found unit name field: {unit_name_field}")

    stratigraphic_order_dict = {unit: index for index, unit in enumerate(stratigraphic_order)}
    # Start editing the layer
    geology_layer.startEditing()
    # Add new field for stratigraphic order if it doesn't exist
    strat_order_field = "strat_order"
    if strat_order_field not in geology_fields:
        from qgis.core import QgsField

        from loopstructural.gui.compatibility import QVariantCompat

        new_field = QgsField(strat_order_field, QVariantCompat.Int)
        geology_layer.dataProvider().addAttributes([new_field])
        geology_layer.updateFields()
        if updater:
            updater(f"Added new field for stratigraphic order: {strat_order_field}")
    # Update stratigraphic order values
    for feature in geology_layer.getFeatures():
        unit_name = feature[unit_name_field]
        strat_order_value = stratigraphic_order_dict.get(unit_name, None)
        if strat_order_value is not None:
            geology_layer.changeAttributeValue(
                feature.id(),
                geology_layer.fields().indexFromName(strat_order_field),
                strat_order_value,
            )
    # Commit changes
    geology_layer.commitChanges()
    if updater:
        updater("Stratigraphic order painted successfully.")
