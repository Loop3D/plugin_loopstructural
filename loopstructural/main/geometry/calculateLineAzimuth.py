from qgis.core import QgsGeometry, QgsPoint


def calculateAverageAzimuth(line: QgsGeometry):
    """Calculate the average azimuth of a line geometry.

    Args:
        line (QgsGeometry): The line geometry.

    Returns:
        float: The average azimuth of the line.

    """
    if line.isMultipart():
        lines = line.asMultiPolyline()
    else:
        lines = [line.asPolyline()]

    azimuths = []
    for line in lines:
        for i in range(1, len(line)):
            azimuth = QgsPoint(line[i - 1]).azimuth(QgsPoint(line[i]))
            azimuths.append(azimuth)

    return sum(azimuths) / len(azimuths) if azimuths else None
