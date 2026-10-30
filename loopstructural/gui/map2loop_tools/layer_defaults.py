"""Set the default layers of a map2loop tool from the shared layer roles.

The user selects a layer for a role one time. Each tool shows that layer as
its default. The user can select another layer in the tool for one run.
"""

from loopstructural.main import layer_roles


def apply_layer_role_defaults(data_manager, combos, *, unit_field_combo=None):
    """Select the layer of each role in the layer combo boxes.

    Parameters
    ----------
    data_manager : ModellingDataManager or None
        Data manager that has the layer roles.
    combos : dict
        Role name -> `QgsMapLayerComboBox`. A role with no layer does not
        change its combo box.
    unit_field_combo : QgsFieldComboBox, optional
        Combo box of the unit name field of the geology layer. It shows the
        `geology_unit_field` role when the field is in the geology layer.
    """
    if data_manager is None:
        return
    for role, combo in combos.items():
        layer = data_manager.layer_roles.get(role)
        if layer is not None:
            combo.setLayer(layer)
    if unit_field_combo is not None:
        geology = data_manager.layer_roles.get(layer_roles.GEOLOGY)
        field = data_manager.layer_roles.get(layer_roles.GEOLOGY_UNIT_FIELD)
        if geology is not None and field and geology.fields().indexFromName(field) >= 0:
            if unit_field_combo.layer() is None or unit_field_combo.layer().id() != geology.id():
                unit_field_combo.setLayer(geology)
            unit_field_combo.setField(field)


def adopt_geology_role(data_manager, *, geology=None, unit_field=None):
    """Give the geology role the layer that a tool used, if it has no layer.

    The other roles follow the Load Data widgets, so a tool does not set
    them. A role that has a layer does not change. The unit field is set only
    when the geology layer of the role is the layer of the tool.
    """
    if data_manager is None:
        return
    data_manager.adopt_layer_roles(geology=geology)
    current = data_manager.layer_roles.get(layer_roles.GEOLOGY)
    if (
        unit_field
        and geology is not None
        and current is not None
        and current.id() == geology.id()
        and data_manager.layer_roles.get(layer_roles.GEOLOGY_UNIT_FIELD) is None
    ):
        data_manager.layer_roles.set(layer_roles.GEOLOGY_UNIT_FIELD, unit_field)
