import pytest

from loopstructural.gui.data_conversion.configuration import NtgsConfig, NtgsConfigurationModel


def test_model_returns_deep_copy():
    base = NtgsConfig().as_dict()
    model = NtgsConfigurationModel(base_config=base)

    exported = model.as_dict()
    exported["geology"]["unitname_column"] = "CustomFormation"

    assert model.get_value("geology", "unitname_column") == base["geology"]["unitname_column"]


def test_set_value_coerces_lists():
    model = NtgsConfigurationModel()
    model.set_value("geology", "ignore_lithology_codes", "cover, Unknown , ,")

    assert model.get_value("geology", "ignore_lithology_codes") == ["cover", "Unknown"]


def test_update_values_casts_to_string():
    model = NtgsConfigurationModel()
    model.update_values("fault", {"dip_null_value": -123})

    assert model.get_value("fault", "dip_null_value") == "-123"


def test_unknown_data_type_raises():
    model = NtgsConfigurationModel()
    with pytest.raises(KeyError):
        model.set_value("unknown", "some_field", "value")
