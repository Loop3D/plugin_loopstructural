"""Tests for the object registry of the viewer (see
loopstructural/gui/visualisation/object_registry.py). No Qt or viewer is needed.
"""

from loopstructural.gui.visualisation.object_registry import (
    MODEL_GROUP,
    NO_FEATURE_GROUP,
    ObjectRegistry,
    ViewerObject,
)


def make(name, **kwargs):
    return ViewerObject(name, mesh=object(), **kwargs)


def test_add_get_remove():
    registry = ObjectRegistry()
    obj = registry.add(make("a"))
    assert registry.get("a") is obj
    assert "a" in registry and len(registry) == 1
    assert registry.remove("a") is obj
    assert registry.get("a") is None
    assert registry.get(None) is None
    assert registry.remove("a") is None


def test_adding_the_same_name_replaces_the_object():
    registry = ObjectRegistry()
    registry.add(make("a", isovalue=1.0))
    new = registry.add(make("a", isovalue=2.0))
    assert len(registry) == 1
    assert registry.get("a") is new


def test_unique_name():
    registry = ObjectRegistry()
    assert registry.unique_name("section") == "section"
    registry.add(make("section"))
    assert registry.unique_name("section") == "section_2"
    registry.add(make("section_2"))
    assert registry.unique_name("section") == "section_3"


def test_rebuildable_objects():
    registry = ObjectRegistry()
    registry.add(make("iso", source_type="feature_isosurface", source_feature="f"))
    registry.add(make("fold", source_type="fold_constraint_axis", source_feature="f"))
    registry.add(make("from_file"))
    registry.add(make("layer", source_type="unknown"))
    assert [o.name for o in registry.rebuildable()] == ["iso", "fold"]


def test_out_of_date_names():
    registry = ObjectRegistry()
    registry.add(make("a", out_of_date=True))
    registry.add(make("b"))
    assert registry.out_of_date() == ["a"]


def test_stratigraphy_colours_only_when_the_topography_is_coloured():
    assert make("s", source_type="block_model").uses_stratigraphy_colours
    plain = make("t", source_type="topography_surface", metadata={"coloured": False})
    coloured = make("t", source_type="topography_surface", metadata={"coloured": True})
    assert not plain.uses_stratigraphy_colours
    assert coloured.uses_stratigraphy_colours


def test_source_values_can_be_used_to_add_the_object_again():
    obj = make(
        "iso",
        source_type="feature_isosurface",
        source_feature="f",
        isovalue=0.5,
        metadata={"a": 1},
    )
    assert obj.is_isosurface
    assert obj.source_values() == {
        "source_feature": "f",
        "source_type": "feature_isosurface",
        "isovalue": 0.5,
        "metadata": {"a": 1},
        "out_of_date": False,
        "threshold": None,
    }


def test_update_kwargs_keeps_the_other_settings():
    obj = make("a", kwargs={"opacity": 0.5, "cmap": "viridis"})
    obj.update_kwargs(opacity=0.2)
    assert obj.kwargs == {"opacity": 0.2, "cmap": "viridis"}


def test_group_by_feature():
    registry = ObjectRegistry()
    registry.add(make("z_iso_1", source_feature="Fault_1", isovalue=1.0))
    registry.add(make("z_iso_0", source_feature="Fault_1", isovalue=0.0))
    registry.add(make("box", source_feature="__model__"))
    registry.add(make("file"))
    registry.add(make("surface", source_feature="Basement"))
    groups = registry.grouped_by_feature()
    assert [name for name, _ in groups] == ["Basement", "Fault_1", MODEL_GROUP, NO_FEATURE_GROUP]
    assert [o.name for o in dict(groups)["Fault_1"]] == ["z_iso_0", "z_iso_1"]
