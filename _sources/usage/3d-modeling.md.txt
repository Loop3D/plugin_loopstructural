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
