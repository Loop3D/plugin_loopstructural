"""configuration helpers used by the data conversion UI."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, MutableMapping


class Config:
    """Container for the default NTGS configuration."""

    def __init__(self) -> None:
        self.fold_config = {
            "structtype_column": "FoldType",
            "fold_text": "'Anticline','Syncline','Antiform','Synform','Monocline','Monoform','Neutral','Fold axis','Overturned syncline'",
            "description_column": "Desc",
            "synform_text": "FoldType",
            "foldname_column": "FoldName",
            "objectid_column": "OBJECTID",
            "tightness_column": "IntlimbAng",
            "axial_plane_dipdir_column": "AxPlDipDir",
            "axial_plane_dip_column": "AxPlDip",
        }

        self.fault_config = {
            "orientation_type": "dip direction",
            "structtype_column": "FaultType",
            "fault_text": "'Thrust','Reverse','Normal','Shear zone','Strike-slip','Thrust','Unknown'",
            "dip_null_value": "-999",
            "dipdir_flag": "num",
            "dipdir_column": "DipDir",
            "dip_column": "Dip",
            "dipestimate_column": "DipEstimate",
            "dipestimate_text": "'NORTH_EAST','NORTH',<rest of cardinals>,'NOT ACCESSED'",
            "displacement_column": "Displace",
            "displacement_text": "'1m-100m', '100m-1km', '1km-5km', '>5km'",
            "fault_length_column": "FaultLen",
            "fault_length_text": "Small (0-5km),Medium (5-30km),Large (30-100km),Regional (>100km),Unclassified",
            "name_column": "FaultName",
            "objectid_column": "OBJECTID",
        }

        self.geology_config = {
            "unitname_column": "Formation",
            "alt_unitname_column": "Formation",
            "group_column": "Group",
            "supergroup_column": "Supergroup",
            "description_column": "LithDescn1",
            "minage_column": "AgeMin",
            "maxage_column": "AgeMax",
            "rocktype_column": "LithClass",
            "alt_rocktype_column": "RockCat",
            "sill_text": "RockCat",
            "intrusive_text": "RockCat",
            "volcanic_text": "RockCat",
            "objectid_column": "OBJECTID",
            "ignore_lithology_codes": ["cover", "Unknown"],
        }

        self.structure_config = {
            "orientation_type": "dip direction",
            "dipdir_column": "DipDir",
            "dip_column": "Dip",
            "description_column": "FeatDesc",
            "bedding_text": "ObsType",
            "overturned_column": "Desc",
            "overturned_text": "overturned",
            "objectid_column": "OBJECTID",
        }

        self.config_map = {
            "geology": self.geology_config,
            "structure": self.structure_config,
            "fault": self.fault_config,
            "fold": self.fold_config,
        }

    def __getitem__(self, datatype: str) -> Dict[str, Any]:
        return self.config_map[datatype]

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return a deep copy of the configuration map."""
        return deepcopy(self.config_map)


def _coerce_config_value(template_value: Any, new_value: Any) -> Any:
    """Coerce user supplied values into the template format."""
    if isinstance(template_value, list):
        if isinstance(new_value, list):
            return new_value
        if new_value in (None, ""):
            return []
        if isinstance(new_value, str):
            return [item.strip() for item in new_value.split(",") if item.strip()]
        return [str(new_value)]

    if isinstance(template_value, (int, float)):
        try:
            return type(template_value)(new_value)
        except (TypeError, ValueError):
            return template_value

    if template_value is None:
        return new_value

    if new_value is None:
        return ""

    return str(new_value)


class ConfigurationState:
    """State holder for the NTGS configuration mapping."""

    def __init__(self, *, base_config: MutableMapping[str, Dict[str, Any]] | None = None):
        self._config = deepcopy(base_config) if base_config is not None else Config().as_dict()

    def data_types(self) -> Iterable[str]:
        """Return the supported data types."""
        return self._config.keys()

    def get_config_for_type(self, data_type: str) -> Dict[str, Any]:
        """Return a copy of the configuration for a single data type."""
        self._ensure_data_type(data_type)
        return deepcopy(self._config[data_type])

    def set_value(self, data_type: str, key: str, value: Any) -> None:
        """Update a single configuration entry."""
        self._ensure_data_type(data_type)
        template_value = self._config[data_type].get(key)
        self._config[data_type][key] = _coerce_config_value(template_value, value)

    def update_values(self, data_type: str, updates: Dict[str, Any]) -> None:
        """Bulk update configuration entries for a type."""
        for key, value in updates.items():
            self.set_value(data_type, key, value)

    def get_value(self, data_type: str, key: str) -> Any:
        """Return the stored value for a configuration entry."""
        self._ensure_data_type(data_type)
        return self._config[data_type].get(key)

    def as_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return a deep copy of the entire configuration map."""
        return deepcopy(self._config)

    def _ensure_data_type(self, data_type: str) -> None:
        if data_type not in self._config:
            raise KeyError(f"Unknown data type '{data_type}'")
