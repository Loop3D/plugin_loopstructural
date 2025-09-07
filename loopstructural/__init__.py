#! python3

# ----------------------------------------------------------
# Copyright (C) 2015 Martin Dobias
# ----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# --------------------------------------------------------------------


def classFactory(iface):
    """Load the plugin class.

    Parameters
    ----------
    iface : QgsInterface
        A QGIS interface instance provided by QGIS when loading plugins.

    Returns
    -------
    LoopstructuralPlugin
        An instance of the plugin class initialized with `iface`.
    """
    from .plugin_main import LoopstructuralPlugin

    return LoopstructuralPlugin(iface)
