import pandas as pd
import geopandas as gpd
from typing import Callable
from abc import ABC, abstractmethod
class BaseSampler(ABC):
    """Base class for samplers."""

    @abstractmethod
    def __call__(self, line: gpd.GeoDataFrame, dem: Callable, use_z: bool) -> pd.DataFrame:
        """Sample the line and return a DataFrame with X, Y, Z coordinates and attributes."""
        pass
class RegularSpacingSampler(BaseSampler):
    def __init__(self, spacing: float):
        self.spacing = spacing
    def __call__(self, line: gpd.GeoDataFrame, dem: Callable, use_z: bool) -> pd.DataFrame:
        """Sample the line at regular intervals and return a DataFrame with X, Y, Z coordinates and attributes."""
        points = []
        feature_id = 0
        if line is None:
            return pd.DataFrame(points, columns=['X', 'Y', 'Z', 'feature_id'])
        for geom in line.geometry:
            attributes = line.iloc[feature_id].to_dict()
            attributes.pop('geometry', None)  # Remove geometry from attributes
            if geom.geom_type == 'LineString':
                length = geom.length
                num_points = max(int(length // self.spacing), 1)
                for i in range(num_points + 1):
                    point = geom.interpolate(i * self.spacing)
                    x, y = point.x, point.y
                    # Use Z from geometry if available, otherwise use DEM
                    if use_z and hasattr(point, 'z'):
                        z = point.z
                    else:
                        z = dem(x, y)
                    points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            elif geom.geom_type == 'MultiLineString':
                for l in geom.geoms:
                    length = l.length
                    num_points = max(int(length // self.spacing), 1)
                    for i in range(num_points + 1):
                        point = l.interpolate(i * self.spacing)
                        x, y = point.x, point.y
                        # Use Z from geometry if available, otherwise use DEM
                        if use_z and hasattr(point, 'z'):
                            z = point.z
                        else:
                            z = dem(x, y)
                        points.append({'X': x, 'Y': y, 'Z': z, 'feature_id': feature_id, **attributes})
            elif geom.geom_type == 'Point':
                coords = list(geom.coords[0])
                # Use Z from geometry if available, otherwise use DEM
                if use_z and len(coords) > 2:
                    z = coords[2]
                elif dem is not None:
                    z = dem(coords[0], coords[1])
                else:
                    z = 0
                points.append({'X': coords[0], 'Y': coords[1], 'Z': z, 'feature_id': feature_id, **attributes})
            feature_id += 1
        df = pd.DataFrame(points)
        return df
class AllSampler(BaseSampler):
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

                coords = list(geom.coords[0])
                # Use Z from geometry if available, otherwise use DEM
                if use_z and len(coords) > 2:
                    z = coords[2]
                elif dem is not None:
                    z = dem(coords[0], coords[1])
                else:
                    z = 0
                points.append({'X': coords[0], 'Y': coords[1], 'Z': z, 'feature_id': feature_id, **attributes})
            feature_id += 1
        df = pd.DataFrame(points)
        return df