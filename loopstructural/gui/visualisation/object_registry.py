"""The objects of the 3D viewer, and the information to build them again.

No Qt code. The viewer owns one `ObjectRegistry`. The widgets read and change
the objects only through it.
"""

from typing import Any, Dict, Iterator, List, Optional, Tuple

# Objects that are built from one feature of the model, by `source_type`
FEATURE_SOURCE_TYPES = frozenset(
    {
        'feature_scalar',
        'feature_surface',
        'feature_isosurface',
        'feature_vector',
        'feature_vectors',
        'feature_points',
        'feature_data',
    }
)
# Objects that are coloured by the stratigraphic column
STRATIGRAPHY_COLOURED_SOURCE_TYPES = frozenset(
    {'cross_section_plane', 'cross_section_line', 'block_model'}
)
# Objects that the update action can build again from the model
REBUILDABLE_SOURCE_TYPES = FEATURE_SOURCE_TYPES | frozenset(
    {
        'bounding_box',
        'fault_surface',
        'stratigraphic_surface',
        'cross_section_plane',
        'cross_section_line',
        'block_model',
        'topography_surface',
    }
)
FOLD_CONSTRAINT_PREFIX = 'fold_constraint_'

# Text for the object list: the group of objects without a source feature
NO_FEATURE_GROUP = 'Other objects'
MODEL_GROUP = 'Model'


class ViewerObject:
    """One mesh in the viewer, with its source and its display settings."""

    def __init__(
        self,
        name: str,
        mesh,
        actor=None,
        kwargs: Optional[Dict[str, Any]] = None,
        source_feature: Optional[str] = None,
        source_type: Optional[str] = None,
        isovalue: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        out_of_date: bool = False,
        threshold: Optional[Dict[str, Any]] = None,
        display_mesh=None,
    ):
        self.name = name
        self.mesh = mesh
        self.actor = actor
        # the arguments that were given to `add_mesh`
        self.kwargs: Dict[str, Any] = dict(kwargs or {})
        self.source_feature = source_feature
        self.source_type = source_type
        self.isovalue = isovalue
        self.metadata: Dict[str, Any] = dict(metadata or {})
        self.out_of_date = out_of_date
        self.threshold = dict(threshold) if threshold else None
        # the part of `mesh` that is shown (the mesh without a filter)
        self.display_mesh = display_mesh if display_mesh is not None else mesh
        # the colour that the user picked
        self.color: Optional[Tuple[float, float, float]] = None

    @property
    def source_type_text(self) -> str:
        return self.source_type or ''

    @property
    def is_rebuildable(self) -> bool:
        source_type = self.source_type_text
        return source_type in REBUILDABLE_SOURCE_TYPES or source_type.startswith(
            FOLD_CONSTRAINT_PREFIX
        )

    @property
    def uses_stratigraphy_colours(self) -> bool:
        if self.source_type_text in STRATIGRAPHY_COLOURED_SOURCE_TYPES:
            return True
        return self.source_type_text == 'topography_surface' and bool(self.metadata.get('coloured'))

    @property
    def is_isosurface(self) -> bool:
        return self.source_type == 'feature_isosurface'

    def source_values(self) -> Dict[str, Any]:
        """The source values as keyword arguments for `add_mesh_object`."""
        return {
            'source_feature': self.source_feature,
            'source_type': self.source_type,
            'isovalue': self.isovalue,
            'metadata': self.metadata,
            'out_of_date': bool(self.out_of_date),
            'threshold': self.threshold,
        }

    def update_kwargs(self, **values) -> None:
        """Change the stored display settings."""
        self.kwargs = {**self.kwargs, **values}


class ObjectRegistry:
    """The viewer objects by name, in the order they were added."""

    def __init__(self):
        self._objects: Dict[str, ViewerObject] = {}

    def __contains__(self, name: str) -> bool:
        return name in self._objects

    def __len__(self) -> int:
        return len(self._objects)

    def __iter__(self) -> Iterator[ViewerObject]:
        return iter(list(self._objects.values()))

    def get(self, name: Optional[str]) -> Optional[ViewerObject]:
        """Return the object with this name, or None."""
        if name is None:
            return None
        return self._objects.get(name)

    def names(self) -> List[str]:
        return list(self._objects)

    def add(self, obj: ViewerObject) -> ViewerObject:
        """Add an object. An object with the same name is replaced."""
        self._objects[obj.name] = obj
        return obj

    def remove(self, name: str) -> Optional[ViewerObject]:
        return self._objects.pop(name, None)

    def unique_name(self, base: str) -> str:
        """Return `base`, or `base_2`, `base_3`, ... if the name is used."""
        if base not in self._objects:
            return base
        i = 2
        while f'{base}_{i}' in self._objects:
            i += 1
        return f'{base}_{i}'

    def rebuildable(self) -> List[ViewerObject]:
        return [obj for obj in self if obj.is_rebuildable]

    def out_of_date(self) -> List[str]:
        return [obj.name for obj in self if obj.out_of_date]

    def of_feature(self, feature: str, source_type: Optional[str] = None) -> List[ViewerObject]:
        """The objects that are built from a feature."""
        return [
            obj
            for obj in self
            if obj.source_feature == feature
            and (source_type is None or obj.source_type == source_type)
        ]

    def grouped_by_feature(self) -> List[Tuple[str, List[ViewerObject]]]:
        """The objects in groups by source feature, sorted by group name and
        then by object name. Objects without a feature are in the last group.
        """
        groups: Dict[str, List[ViewerObject]] = {}
        for obj in self:
            if obj.source_feature == '__model__':
                key = MODEL_GROUP
            else:
                key = obj.source_feature or NO_FEATURE_GROUP
            groups.setdefault(key, []).append(obj)
        special = (MODEL_GROUP, NO_FEATURE_GROUP)
        keys = sorted(k for k in groups if k not in special) + [k for k in special if k in groups]
        return [(k, sorted(groups[k], key=lambda o: o.name)) for k in keys]
