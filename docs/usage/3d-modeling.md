# 3D Modelling Background

### Background on 3D Modeling

A **3D model** is a mathematical representation of a three-dimensional object. In the context of geology, 3D models are used to visualize and analyze the subsurface structure of the Earth. These models are constructed by integrating various types of geological data, such as borehole logs, geological maps, geophysical surveys, and structural measurements. The goal is to create a coherent representation of the subsurface that can be used for exploration, resource management, and scientific research.



#### Implicit Modeling

Implicit modeling is a modern approach to constructing 3D geological models. Unlike traditional methods that rely on explicit surfaces and manual digitization, implicit modeling uses mathematical functions to represent geological features. These functions are defined over the entire model space and allow for the automatic generation of surfaces, such as stratigraphic boundaries and faults.

Key advantages of implicit modeling include:
- **Efficiency**: Models can be constructed quickly, even with large datasets.
- **Flexibility**: Implicit methods can handle complex geometries and data uncertainties.
- **Automation**: The process is less reliant on manual interpretation, reducing subjectivity.

Implicit modeling has become widely used, enabling geoscientists to create detailed and accurate representations of the Earth's subsurface.

## LoopStructural
LoopStructural is an open-source Python library designed for implicit geological modeling. It provides tools for creating 3D geological models based on various types of input data, including borehole data, surface data, and structural measurements. LoopStructural provides both the implicit modelling algorithms and parameterisation of geological objects.

### Stratigraphic Modelling
In LoopStructural stratigraphic surfaces can be modelled using implicit functions. The function is approximated to fit observations of the surface for example the location of contacts, the orientation of the surface at the location of a contact. Combined with a stratigraphic column which defines the order of the contacts and any unconformable relationships between them, LoopStructural can interpolate a function which approximates the geometry of the surface.  

### Fault modelling
Faults are modelled in LoopStructural by building three implicit functions defining the fault surface, fault slip vector and the fault extent. Combined with a parametric representation of the fault displacement within these coordinates a kinematic model.

## Push the model to GeoViewer

GeoViewer is the advanced 3D viewer of Loop. It is a separate program. The plugin sends the
solved model to it with the `loop-link` package. This is optional: the 3D view of the plugin does
not change.

Install the package in the Python of QGIS: `pip install loop-link`.

1. Start GeoViewer and turn its link on.
2. In the plugin, build the model (step 4). Open **Export** in step 5 and select the
   **GeoViewer** tab.
3. Select the kinds of object to send, and select **Push model to GeoViewer**.

These kinds of object can be sent. Each kind goes into its own group in the group
`LoopStructural model` of the GeoViewer scene.

| Kind | GeoViewer object |
| --- | --- |
| Stratigraphic surfaces, fault surfaces | Surface, with the colour of the unit or fault |
| Stratigraphy volume | Block model with the categories of the units |
| Scalar fields | Block model with the value of each feature on the nodes |
| DEM | Surface with an `elevation` property |
| Data points | Points with the value of the data |
| Orientation data | Vectors with dip direction and dip |
| Vector fields | Vectors of the gradient of each feature |
| Lines | Bounding box of the model, fault traces and basal contacts |

The **Cells** values set the size of the grid of the stratigraphy volume and of the scalar
fields. **Port** is **Automatic** by default: loop_link finds the running viewer and reads the
token that GeoViewer saved. Type a port or a token only if you need to override them.

A new push replaces the objects of the last push. Other objects of the scene stay. The
coordinates are in the CRS of the model, and the scene of GeoViewer keeps its own origin.
