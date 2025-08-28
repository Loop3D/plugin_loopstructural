from LoopStructural.datatypes import BoundingBox
from loopstructural.main.data_manager import default_bounding_box

import json
from qgis.core import QgsMapLayer
import numpy as np
def create_bounding_box_json(layer: QgsMapLayer, xmin: float, xmax: float, ymin: float, ymax: float, zmin: float, zmax: float):
    """Create a bounding box JSON representation."""
    print(f"Creating bounding box with layer={layer}, xmin={xmin}, xmax={xmax}, ymin={ymin}, ymax={ymax}, zmin={zmin}, zmax={zmax}")
    if layer is not None:
        extent = layer.extent()
        print(f"Layer extent: {extent.toString()}")
        if xmin == -9999:
            xmin = extent.xMinimum()
        if xmax == -9999:
            xmax = extent.xMaximum()
        if ymin == -9999:
            ymin = extent.yMinimum()
        if ymax == -9999:
            ymax = extent.yMaximum()
        if zmin == -9999:
            if hasattr(extent, 'zMinimum') and extent.zMinimum() is not None and not np.isnan(extent.zMinimum()):
                zmin = extent.zMinimum()
            else:
                zmin = default_bounding_box['zmin']

        if zmax == -9999:
            if hasattr(extent, 'zMaximum') and extent.zMaximum() is not None and not np.isnan(extent.zMaximum()):
                zmax = extent.zMaximum()
            else:
                zmax = default_bounding_box['zmax']

    # fallback to defaults for any remaining None values
    if xmin is None:
        xmin = default_bounding_box['xmin']
    if xmax is None:
        xmax = default_bounding_box['xmax']
    if ymin is None:
        ymin = default_bounding_box['ymin']
    if ymax is None:
        ymax = default_bounding_box['ymax']
    if zmin is None:
        zmin = default_bounding_box['zmin']
    if zmax is None:
        zmax = default_bounding_box['zmax']

    # ensure all values present
    if xmin is None or xmax is None or ymin is None or ymax is None or zmin is None or zmax is None:
        return None

    # BoundingBox expects origin=[xmin, ymin, zmin] and maximum=[xmax, ymax, zmax]
    bbox = BoundingBox([xmin, ymin, zmin], [xmax, ymax, zmax])
    return json.dumps(bbox.to_dict())