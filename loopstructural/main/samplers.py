import geopandas as gpd
from typing import Callable
import pandas as pd
class AllSampler:
    """This is a simple sampler that just returns all the points, or all of the vertices
    of a line. It will also copy the elevation from the DEM or the elevation set in the data manager.
    """

    def __call__(self, line: gpd.GeoDataFrame, dem: Callable, use_z: bool) -> pd.DataFrame:
        """Sample the line and return a DataFrame with X, Y, Z coordinates and attributes."""
        points = []
        feature_id = 0
        if line is None:
            return pd.DataFrame(points, columns=['X', 'Y', 'Z', 'feature_id'])
        for geom in line.geometry:
            attributes = line.iloc[feature_id].to_dict()
            attributes.pop('geometry', None)  # Remove geometry from attributes
            if geom.geom_type == 'LineString':
                coords = list(geom.coords)
                for coord in coords:
                    x, y = coord[0], coord[1]
                    # Use Z from geometry if available, otherwise use DEM
                    if use_z and len(coord) > 2:
                        z = coord[2]
                    else:
                        z = dem(x, y)
                    points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            elif geom.geom_type == 'MultiLineString':
                for l in geom.geoms:
                    coords = list(l.coords)
                    for coord in coords:
                        x, y = coord[0], coord[1]
                        # Use Z from geometry if available, otherwise use DEM
                        if use_z and len(coord) > 2:
                            z = coord[2]
                        else:
                            z = dem(x, y)
                        points.append(
                            {'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes}
                        )
            elif geom.geom_type == 'Point':
                x, y = geom.x, geom.y
                # Use Z from geometry if available, otherwise use DEM
                if use_z and hasattr(geom, 'z'):
                    z = geom.z
                else:
                    z = dem(x, y)
                points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            feature_id += 1
        df = pd.DataFrame(points)
        return df