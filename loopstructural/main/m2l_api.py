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
from map2loop.thickness_calculator import InterpolatedStructure, StructuralPoint
from osgeo import gdal

from ..main.vectorLayerWrapper import qgsLayerToDataFrame, qgsLayerToGeoDataFrame
from .debug.export import export_debug_package

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


def extract_basal_contacts(
    geology,
    stratigraphic_order,
    faults=None,
    ignore_units=None,
    unit_name_field=None,
    all_contacts=False,
    updater=None,
    debug_manager=None,
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

    Returns
    -------
    dict
        Dictionary containing 'basal_contacts' GeoDataFrame and optionally 'all_contacts' GeoDataFrame.
    """
    geology = qgsLayerToGeoDataFrame(geology)
    if unit_name_field and unit_name_field in geology.columns:
        mask = ~geology[unit_name_field].astype(str).str.strip().isin(ignore_units or [])
        geology = geology[mask].reset_index(drop=True)
        if updater:
            updater(f"filtered by unit name field: {unit_name_field}")
    else:
        if updater:
            updater(f"no unit name field found: {unit_name_field}")

    faults = qgsLayerToGeoDataFrame(faults) if faults else None
    if unit_name_field and unit_name_field != 'UNITNAME' and unit_name_field in geology.columns:
        geology = geology.rename(columns={unit_name_field: 'UNITNAME'})
    # Log parameters via DebugManager if provided
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

    except Exception as e:
        print("Failed to save sampler debug info")
        print(e)

    all_contacts_result = contact_extractor.extract_all_contacts()
    basal_contacts = contact_extractor.extract_basal_contacts(stratigraphic_order)

    if ignore_units:
        basal_contacts = basal_contacts[
            ~basal_contacts['UNITNAME'].astype(str).str.strip().isin(ignore_units)
        ].reset_index(drop=True)
    if all_contacts:
        return {'basal_contacts': basal_contacts, 'all_contacts': all_contacts_result}
    return {'basal_contacts': basal_contacts}


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
    contacts : QgsVectorLayer or GeoDataFrame
        Contacts line layer.
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
    contacts_gdf = qgsLayerToGeoDataFrame(contacts)

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
    # Build relationships DataFrame (contacts without geometry)
    relationships_df = contacts_gdf.copy()
    if 'geometry' in relationships_df.columns:
        relationships_df = relationships_df.drop(columns=['geometry'])
    if 'length' in relationships_df.columns:
        relationships_df = relationships_df.drop(columns=['length'])

    # Prepare all possible arguments
    all_args = {
        'geology_data': geology_gdf,
        'contacts': contacts_gdf,
        'relationships': relationships_df,
        'unit_name_field': unit_name_field,
        'min_age_column': min_age_field,
        'max_age_column': max_age_field,
        'unitname1_field': unitname1_field,
        'unitname2_field': unitname2_field,
        'structure': qgsLayerToGeoDataFrame(structure) if structure is not None else None,
        'dip_field': dip_field,
        'dipdir_field': dipdir_field,
        'orientation_type': orientation_type,
        'dtm': dtm,
        'updater': updater,
        'unit_name_column': unit_name_field,
    }

    # Only pass required arguments to the sorter
    sorter_args = {k: v for k, v in all_args.items() if k in required_args}
    print(f'Calling sorter with args: {sorter_args.keys()}')
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

    except Exception as e:
        print("Failed to save sampler debug info")
        print(e)

    order = sorter.sort(units_df)
    if updater:
        updater(f"Sorting complete: {len(order)} units ordered")

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
            dtm_gdal = gdal.Open(dtm.source())
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

    except Exception as e:
        print("Failed to save sampler debug info")
        print(e)

    return samples


def calculate_thickness(
    geology,
    basal_contacts,
    sampled_contacts,
    structure,
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
    basal_contacts : QgsVectorLayer or GeoDataFrame
        Basal contacts line layer.
    sampled_contacts : QgsVectorLayer or GeoDataFrame
        Sampled contacts point layer.
    structure : QgsVectorLayer or GeoDataFrame
        Structure point layer with orientation data.
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
    basal_contacts_gdf = qgsLayerToGeoDataFrame(basal_contacts)
    basal_contacts_gdf = (
        basal_contacts_gdf.rename(columns={basal_contacts_unit_name: 'basal_unit'})
        if basal_contacts_unit_name
        else basal_contacts_gdf
    )
    sampled_contacts_gdf = qgsLayerToGeoDataFrame(sampled_contacts)
    structure_gdf = qgsLayerToDataFrame(structure)

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

    # Handle dip field
    if dip_field and dip_field != 'DIP' and dip_field in structure_gdf.columns:
        structure_gdf = structure_gdf.rename(columns={dip_field: 'DIP'})

    # Handle dip direction field based on orientation type
    if dipdir_field and dipdir_field in structure_gdf.columns:
        if orientation_type == 'Strike':
            structure_gdf['DIPDIR'] = structure_gdf[dipdir_field].apply(
                lambda val: (val + 90.0) % 360.0 if pd.notna(val) else val
            )
        elif orientation_type == 'Dip Direction':
            structure_gdf = structure_gdf.rename(columns={dipdir_field: 'DIPDIR'})

    # Convert DTM to GDAL dataset if needed
    dtm_gdal = None
    if dtm is not None:
        if hasattr(dtm, 'source'):  # It's a QgsRasterLayer
            dtm_gdal = gdal.Open(dtm.source())
        else:
            dtm_gdal = dtm

    # Run thickness calculator
    if calculator_type == "InterpolatedStructure":
        calculator = InterpolatedStructure(
            bounding_box=bounding_box,
            dtm_data=dtm_gdal,
            is_strike=orientation_type == 'Strike',
            max_line_length=max_line_length,
        )
    else:  # StructuralPoint
        if max_line_length is None:
            raise ValueError("max_line_length parameter is required for StructuralPoint calculator")
        calculator = StructuralPoint(
            bounding_box=bounding_box,
            dtm_data=dtm_gdal,
            is_strike=orientation_type == 'Strike',
            max_line_length=max_line_length,
        )
    if unit_name_field != 'UNITNAME' and unit_name_field in geology_gdf.columns:
        geology_gdf = geology_gdf.rename(columns={unit_name_field: 'UNITNAME'})
    units = geology_gdf.copy()

    units_unique = units.drop_duplicates(subset=['UNITNAME']).reset_index(drop=True)
    units = pd.DataFrame({'name': units_unique['UNITNAME']})
    basal_contacts_gdf['type'] = 'BASAL'  # required by calculator

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
                    'structure': structure_gdf,
                    'geology': geology_gdf,
                    'sampled_contacts': sampled_contacts_gdf,
                },
            )

    except Exception as e:
        print("Failed to save sampler debug info")
        raise e

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
