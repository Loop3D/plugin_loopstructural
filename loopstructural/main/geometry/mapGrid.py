import numpy as np
from qgis.core import QgsPointXY, QgsRaster


def createGrid(boundingBox, dtm):
    """Create a grid from a bounding box and an optional DEM.

    Parameters
    ----------
    boundingBox : object
        Bounding box of the grid. Must provide `corners_global` and `nsteps`.
    dtm : QgsRaster or None
        Digital Terrain Model used to sample Z values (optional).

    Returns
    -------
    numpy.ndarray
        Array of shape (N, 3) with X, Y, Z coordinates for grid points.
    """
    minx, miny, maxx, maxy = boundingBox.corners_global[[0, 2], :2].flatten()
    x = np.linspace(minx, maxx, boundingBox.nsteps[0])
    y = np.linspace(miny, maxy, boundingBox.nsteps[1])
    X, Y = np.meshgrid(x, y)
    Z = np.zeros_like(X)
    if dtm is not None:
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                p = QgsPointXY(X[i, j], Y[i, j])
                z_value = dtm.dataProvider().identify(p, QgsRaster.IdentifyFormatValue)
                if z_value.isValid():
                    z_value = z_value.results()[1]
                else:
                    z_value = -9999
                Z[i, j] = z_value
    pts = np.array([X.flatten(order='f'), Y.flatten(order='f'), Z.flatten(order='f')]).T
    return pts
