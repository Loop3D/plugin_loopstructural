"""Build the meshes of the viewer objects from the geological model.

No Qt code. The widgets call these functions and add the result to the viewer.
Some of them are slow (they can solve the model), so they do not touch the
viewer and are safe to call on a background thread.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pyvista as pv
from LoopStructural.datatypes import VectorPoints

from .cross_section_utils import build_block_model_mesh
from .mesh_scalar_utils import stratigraphic_ids_to_rgb
from .object_registry import FEATURE_SOURCE_TYPES, FOLD_CONSTRAINT_PREFIX

logger = logging.getLogger(__name__)

# Vectors used by the fold constraints in the DiscreteFoldInterpolator.
# direction: gradient . direction = 0 (fold orientation constraint)
# axis: gradient . axis = 0 (fold axis constraint)
# norm: gradient . norm = fold_norm (fold normalisation constraint)
FOLD_CONSTRAINT_LABELS = {
    'direction': "Fold Direction",
    'axis': "Fold Axis",
    'norm': "Fold Norm Direction",
}
FOLD_CONSTRAINT_COLOURS = {
    'direction': (0.2, 0.4, 1.0),
    'axis': (1.0, 0.2, 0.2),
    'norm': (0.1, 0.8, 0.2),
}


def set_stratigraphy_arrays(data, ids, colours) -> None:
    """Store the unit ids and their colours as the 'stratigraphy' and
    'colour' arrays of `data` (a mesh's point_data or cell_data).

    Named arrays (not an RGB array passed straight to the viewer) let the
    object properties panel use the unit ids, and let the update action add
    the object again with the same viewer settings.
    """
    data['stratigraphy'] = np.asarray(ids)
    data['colour'] = stratigraphic_ids_to_rgb(ids, colours)


class MeshBuilder:
    """Build viewer meshes from the model of a model manager."""

    def __init__(self, model_manager):
        self.model_manager = model_manager

    @property
    def model(self):
        return self.model_manager.model

    def vector_scale(self, scale: Optional[float] = None) -> float:
        """Vector length: 5% of the longest side of the model bounding box."""
        autoscale = 1.0
        if self.model is not None:
            autoscale = self.model.bounding_box.length.max() * 0.05
        return autoscale if scale is None else scale * autoscale

    # -- feature meshes --------------------------------------------------

    def scalar_field(self, feature_name: str):
        return self.model[feature_name].scalar_field().vtk()

    def feature_surfaces(self, feature_name: str) -> List[Any]:
        """The surfaces that the model gives for a feature."""
        return list(self.model[feature_name].surfaces())

    def feature_surface(self, feature_name: str, isovalue: Optional[float]):
        feature = self.model[feature_name]
        surfaces = feature.surfaces(isovalue) if isovalue is not None else feature.surfaces()
        if not surfaces:
            raise ValueError(f"Feature '{feature_name}' has no surface at {isovalue}")
        return surfaces[0].vtk()

    def scalar_range(self, feature_name: str) -> Tuple[float, float]:
        """The minimum and maximum of the scalar field of a feature."""
        feature = self.model[feature_name]
        return float(feature.min()), float(feature.max())

    def isosurface(self, feature_name: str, value: float):
        """The isosurface of a feature at one value.

        Raises ValueError if the surface has no geometry (for example when
        the value is outside the range of the field).
        """
        surfaces = self.model[feature_name].surfaces(float(value))
        if not surfaces:
            raise ValueError(f"The isosurface of '{feature_name}' at {value:g} cannot be built")
        mesh = surfaces[0].vtk()
        if getattr(mesh, 'n_points', 1) == 0:
            raise ValueError(f"The isosurface of '{feature_name}' at {value:g} has no geometry")
        return mesh

    def vector_field(self, feature_name: str):
        vector_field = self.model[feature_name].vector_field()
        return vector_field.vtk(scale=self.vector_scale())

    def get_fold(self, feature_name: str):
        try:
            feature = self.model[feature_name]
        except Exception:
            return None
        fold = getattr(feature, 'fold', None)
        if fold is None:
            fold = getattr(getattr(feature, 'builder', None), 'fold', None)
        return fold

    def fold_constraint(self, feature_name: str, constraint: str):
        """Return the vectors of one fold constraint of a folded feature as
        a mesh, or None if the feature is not folded or the vectors are not
        defined.

        The vectors are evaluated on the model grid, in the same way as the
        interpolator evaluates them on the element barycentres.
        """
        fold = self.get_fold(feature_name)
        if fold is None:
            logger.info(f"Feature {feature_name} is not folded")
            return None
        feature = self.model[feature_name]
        # make sure the fold rotation angles are fitted
        feature.builder.up_to_date()
        bounding_box = self.model.bounding_box
        points = bounding_box.reproject(bounding_box.cell_centres())
        direction, axis, norm = fold.get_deformed_orientation(points)
        vectors = np.array({'direction': direction, 'axis': axis, 'norm': norm}[constraint])
        if vectors.shape != points.shape:
            # some fold settings (e.g. invert_norm) return a subset of the vectors
            logger.warning(
                f"Fold {constraint} vectors do not match the grid points ({vectors.shape} != {points.shape})"
            )
            return None
        length = np.linalg.norm(vectors, axis=1)
        mask = np.all(np.isfinite(vectors), axis=1) & (length > 0)
        if not np.any(mask):
            logger.warning(f"Fold {constraint} vectors for {feature_name} are not defined")
            return None
        vectors = vectors[mask] / length[mask, None]
        vector_points = VectorPoints(points[mask], vectors, f'{feature_name}_fold_{constraint}')
        return vector_points.vtk(scale=self.vector_scale())

    def data_meshes(self, feature_name: str) -> List[Tuple[str, Any, str]]:
        """Return (name, mesh, source_type) for each data set of a feature."""
        meshes = []
        for d in self.model[feature_name].get_data():
            d.locations = self.model.rescale(d.locations)
            if issubclass(type(d), VectorPoints):
                # tolerance is None means all points are shown
                meshes.append(
                    (
                        f'{feature_name}_{d.name}_points',
                        d.vtk(scale=self.vector_scale(), tolerance=None),
                        'feature_points',
                    )
                )
            else:
                meshes.append((f'{feature_name}_{d.name}', d.vtk(), 'feature_data'))
        return meshes

    # -- model meshes ----------------------------------------------------

    def bounding_box(self):
        return self.model.bounding_box.vtk().outline()

    def fault_surface(self, name: str):
        for surface in self.model.get_fault_surfaces():
            if str(surface.name) == str(name):
                return surface
        raise ValueError(f"Fault surface '{name}' is not in the model")

    def stratigraphic_surface(self, name: str):
        for surface in self.model.get_stratigraphic_surfaces():
            if str(surface.name) == str(name):
                return surface
        raise ValueError(f"Stratigraphic surface '{name}' is not in the model")

    def topography(self):
        """The DEM sampled across the model extent, with an 'Elevation' array."""
        xx, yy, zz = self.model_manager.sample_dem_grid()
        return self.topography_from_grid(xx, yy, zz)

    @staticmethod
    def topography_from_grid(xx, yy, zz):
        mesh = pv.StructuredGrid(xx, yy, zz)
        mesh['Elevation'] = mesh.points[:, 2]
        return mesh

    def block_model(self, ncells):
        bb = self.model.bounding_box
        return build_block_model_mesh(bb.origin, bb.maximum, ncells)

    # -- stratigraphy colours -------------------------------------------

    def stratigraphy_metadata(self, colours) -> Dict[str, Any]:
        """Unit names and colours, indexed by unit id, for the unit check
        boxes of the object properties panel."""
        return {
            'unit_names': list(self.model_manager.get_stratigraphic_unit_names()),
            'unit_colours': list(colours),
        }

    def colour_by_stratigraphy(self, points, data, metadata: Dict[str, Any]) -> None:
        """Colour a mesh by the stratigraphic unit at `points`, and store
        the unit names and colours in `metadata`."""
        ids = self.model_manager.evaluate_stratigraphy_on_points(points)
        colours = self.model_manager.get_stratigraphic_column_colours()
        set_stratigraphy_arrays(data, ids, colours)
        metadata.update(self.stratigraphy_metadata(colours))

    # -- build again -----------------------------------------------------

    def rebuild(self, spec: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
        """Build one viewer object again from the current model.

        `spec` has the keys name, source_type, source_feature, isovalue and
        metadata (and mesh, for a cross section). Returns (mesh, overrides),
        where overrides are viewer settings that come from the model (e.g. a
        unit colour). `spec['metadata']` is updated with new values from the
        model (e.g. the unit names). Raises if the object cannot be built.
        """
        source_type = spec['source_type']
        feature_name = spec['source_feature']
        metadata = spec['metadata']

        if source_type in FEATURE_SOURCE_TYPES or source_type.startswith(FOLD_CONSTRAINT_PREFIX):
            if feature_name is None or self.model.get_feature_by_name(feature_name) is None:
                raise ValueError(f"Feature '{feature_name}' is not in the model")

        overrides: Dict[str, Any] = {}
        if source_type == 'feature_scalar':
            mesh = self.scalar_field(feature_name)
        elif source_type == 'feature_surface':
            mesh = self.feature_surface(feature_name, spec['isovalue'])
        elif source_type == 'feature_isosurface':
            if spec['isovalue'] is None:
                raise ValueError("The isosurface has no value")
            mesh = self.isosurface(feature_name, spec['isovalue'])
        elif source_type in ('feature_vector', 'feature_vectors'):
            mesh = self.vector_field(feature_name)
        elif source_type.startswith(FOLD_CONSTRAINT_PREFIX):
            constraint = source_type[len(FOLD_CONSTRAINT_PREFIX) :]
            mesh = self.fold_constraint(feature_name, constraint)
            if mesh is None:
                raise ValueError("The fold constraint vectors are not defined")
        elif source_type in ('feature_points', 'feature_data'):
            meshes = {name: m for name, m, _ in self.data_meshes(feature_name)}
            if spec['name'] not in meshes:
                raise ValueError(f"Feature '{feature_name}' has no data for this object")
            mesh = meshes[spec['name']]
        elif source_type == 'bounding_box':
            mesh = self.bounding_box()
        elif source_type == 'fault_surface':
            mesh = self.fault_surface(feature_name).vtk()
        elif source_type == 'stratigraphic_surface':
            surface = self.stratigraphic_surface(feature_name)
            mesh = surface.vtk()
            overrides['color'] = surface.colour
        elif source_type in ('cross_section_plane', 'cross_section_line'):
            mesh = spec['mesh']
            self.colour_by_stratigraphy(mesh.points, mesh.point_data, metadata)
        elif source_type == 'block_model':
            mesh = self.block_model(metadata['ncells'])
            self.colour_by_stratigraphy(mesh.cell_centers().points, mesh.cell_data, metadata)
        elif source_type == 'topography_surface':
            mesh = self.topography()
            if metadata.get('coloured'):
                self.colour_by_stratigraphy(mesh.points, mesh.point_data, metadata)
        else:
            raise ValueError(f"Cannot update objects of type '{source_type}'")

        if getattr(mesh, 'n_points', 1) == 0:
            raise ValueError("The object has no geometry in the current model")
        return mesh, overrides
