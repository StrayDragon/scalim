import copy
from types import SimpleNamespace
from typing import List

import pytest

from scalim_misc.yaml_schema_generator import SchemaBuilder, _allow_yaml_merge_key_in_property_names, _build_default_types_module


def test_schema_builder_schema_for_type_list_hits_container_branch() -> None:
    builder = SchemaBuilder()

    schema = builder._schema_for_type(List[str], allow_import=True)  # noqa: SLF001
    assert schema["type"] == "array"
    assert schema["items"] == {"type": "string"}


def test_schema_builder_build_demand_schema_allows_missing_markdown_description_in_meta() -> None:
    base_types = _build_default_types_module()
    meta = dict(base_types.DEMAND_SCHEMA_META)
    meta.pop("markdownDescription", None)

    types_mod = SimpleNamespace(**{**vars(base_types), "DEMAND_SCHEMA_META": meta})
    builder = SchemaBuilder(types_module=types_mod)

    schema = builder.build_demand_schema()
    assert schema["type"] == "object"
    assert "properties" in schema


def test_schema_builder_build_demand_schema_skips_additional_properties_when_unset() -> None:
    base_types = _build_default_types_module()

    class DemandConfigNoAdditional(base_types.DemandConfig):
        SCHEMA_ADDITIONAL_PROPERTIES = None

    types_mod = SimpleNamespace(**{**vars(base_types), "DemandConfig": DemandConfigNoAdditional})
    builder = SchemaBuilder(types_module=types_mod)

    schema = builder.build_demand_schema()
    assert "additionalProperties" not in schema


def test_schema_builder_build_scalim_yaml_schema_allows_missing_markdown_description_in_meta() -> None:
    base_types = _build_default_types_module()
    meta = dict(base_types.SCALIM_YAML_SCHEMA_META)
    meta.pop("markdownDescription", None)

    types_mod = SimpleNamespace(**{**vars(base_types), "SCALIM_YAML_SCHEMA_META": meta})
    builder = SchemaBuilder(types_module=types_mod)

    schema = builder.build_scalim_yaml_schema()
    assert "definitions" in schema
    assert schema["oneOf"][0]["type"] == "null"


def test_schema_builder_assert_numeric_constraints_typed_rejects_empty_type_list() -> None:
    builder = SchemaBuilder()
    with pytest.raises(ValueError, match=r"numeric constraints"):
        builder._assert_numeric_constraints_typed(  # noqa: SLF001
            {"type": [], "minimum": 1},
            context="test",
        )


def test_schema_builder_assert_numeric_constraints_typed_rejects_non_str_and_non_list_type() -> None:
    builder = SchemaBuilder()
    with pytest.raises(ValueError, match=r"numeric constraints"):
        builder._assert_numeric_constraints_typed(  # noqa: SLF001
            {"type": {}, "minimum": 1},
            context="test",
        )


def test_schema_builder_assert_numeric_constraints_typed_ignores_non_str_items_in_type_list() -> None:
    builder = SchemaBuilder()
    builder._assert_numeric_constraints_typed(  # noqa: SLF001
        {"type": [1, "integer"], "minimum": 1},
        context="test",
    )


def test_schema_builder_expand_meta_items_choices_keeps_existing_items_schema() -> None:
    builder = SchemaBuilder()
    expanded = builder._expand_meta(  # noqa: SLF001
        {"items": {"type": "string"}, "items_choices": [1, 2]},
    )
    assert expanded["items"]["enum"] == [1, 2]


def test_schema_builder_expand_meta_items_choices_ignores_non_dict_items_schema() -> None:
    builder = SchemaBuilder()
    expanded = builder._expand_meta(  # noqa: SLF001
        {"items": "x", "items_choices": [1]},
    )
    assert expanded["items"] == "x"


def test_schema_builder_ref_schema_returns_empty_when_schema_name_is_not_str() -> None:
    builder = SchemaBuilder()

    class Dummy:
        SCHEMA_NAME = 1

    assert builder._ref_schema(Dummy) == {}  # noqa: SLF001


def test_allow_yaml_merge_key_in_property_names_wraps_pattern_property_names_and_is_idempotent() -> None:
    schema = {
        "type": "object",
        "propertyNames": {"pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$"},
    }
    _ = _allow_yaml_merge_key_in_property_names(schema)
    assert schema["propertyNames"]["anyOf"][0] == {"const": "<<"}
    assert schema["propertyNames"]["anyOf"][1] == {"pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$"}

    snapshot = copy.deepcopy(schema)
    _ = _allow_yaml_merge_key_in_property_names(schema)
    assert schema == snapshot


def test_allow_yaml_merge_key_in_property_names_keeps_existing_anyof_const() -> None:
    schema = {
        "type": "object",
        "properties": {
            "fields": {
                "type": "object",
                "propertyNames": {"anyOf": [{"const": "<<"}, {"pattern": "^[a-z]+$"}]},
            },
        },
    }
    snapshot = copy.deepcopy(schema)
    _ = _allow_yaml_merge_key_in_property_names(schema)
    assert schema == snapshot


def test_allow_yaml_merge_key_in_property_names_keeps_existing_enum() -> None:
    schema = {"type": "object", "propertyNames": {"enum": ["<<", "a"]}}
    snapshot = copy.deepcopy(schema)
    _ = _allow_yaml_merge_key_in_property_names(schema)
    assert schema == snapshot


def test_allow_yaml_merge_key_in_property_names_wraps_ref_property_names() -> None:
    schema = {"type": "object", "propertyNames": {"$ref": "#/definitions/field_id"}}
    _ = _allow_yaml_merge_key_in_property_names(schema)
    assert schema["propertyNames"]["anyOf"][0] == {"const": "<<"}
    assert schema["propertyNames"]["anyOf"][1] == {"$ref": "#/definitions/field_id"}
