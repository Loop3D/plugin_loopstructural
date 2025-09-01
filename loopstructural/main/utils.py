import geopandas as gpd
from typing import Callable
from .samplers import AllSampler
def process_gdf_for_faults(*,fault_trace: gpd.GeoDataFrame,
                           sampler=AllSampler(),
                           dem_function: Callable,
                           use_z_coordinate: bool,
                           fault_name_field: str = None,
                           fault_dip_field: str = None,
                           fault_displacement_field: str = None,
                           fault_pitch_field: str = None) -> gpd.GeoDataFrame:
    fault_points = sampler(fault_trace, dem_function, use_z_coordinate)
    cols = ['X', 'Y', 'Z']
    if fault_name_field is not None and fault_name_field in fault_points.columns:
        fault_points['fault_name'] = fault_points[fault_name_field].astype(str)
    else:
        fault_points['fault_name'] = fault_points['feature_id'].astype(str)
    if fault_dip_field is not None and fault_dip_field in fault_points.columns:
        fault_points['dip'] = fault_points[fault_dip_field]
        cols.append('dip')
    if (
        fault_displacement_field is not None
        and fault_displacement_field in fault_points.columns
    ):
        fault_points['displacement'] = fault_points[fault_displacement_field]
        cols.append('displacement')
    if fault_pitch_field is not None and fault_pitch_field in fault_points.columns:
        fault_points['pitch'] = fault_points[fault_pitch_field]
        cols.append('pitch')
    return fault_points, cols