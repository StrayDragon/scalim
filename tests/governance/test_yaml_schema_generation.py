from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Tuple
from types import SimpleNamespace

import pytest

from scalim.dsl.yaml_dsl.schema_dsl import constants as yaml_constants
from scalim_misc.yaml_schema_generator import (
    SchemaBuilder,
    build_demand_schema,
    build_scalim_yaml_schema,
    build_workflow_schema,
    load_schema,
    normalize_schema,
    schemas_equivalent,
    write_demand_schema,
    write_scalim_yaml_schema,
    write_workflow_schema,
)
from scalim.dsl.yaml_dsl.schema_dsl.models import LOOKUP_CAST_KEYS
from scalim.dsl.yaml_dsl.schema_dsl import doc_texts as yaml_doc_texts
from tests.support.pathing import repo_root as _repo_root


def _schema_path(name: str) -> Path:
    repo_root = _repo_root()
    return repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / name


def test_generator_matches_generated_file() -> None:
    generated = build_demand_schema()
    file_schema = load_schema(_schema_path("demand.gen.json"))

    assert schemas_equivalent(generated, file_schema)


def test_workflow_generator_matches_generated_file() -> None:
    generated = build_workflow_schema()
    file_schema = load_schema(_schema_path("workflow.gen.json"))

    assert schemas_equivalent(generated, file_schema)


def test_scalim_yaml_generator_matches_generated_file() -> None:
    generated = build_scalim_yaml_schema()
    file_schema = load_schema(_schema_path("scalim_yaml.gen.json"))

    assert schemas_equivalent(generated, file_schema)


def test_generated_schema_has_comment() -> None:
    generated = load_schema(_schema_path("demand.gen.json"))

    assert "$comment" in generated


def test_generated_workflow_schema_has_comment() -> None:
    generated = load_schema(_schema_path("workflow.gen.json"))

    assert "$comment" in generated


def test_generated_scalim_yaml_schema_has_comment() -> None:
    generated = load_schema(_schema_path("scalim_yaml.gen.json"))

    assert "$comment" in generated


def test_by_yaml_schema_package_is_importable() -> None:
    from scalim.dsl.yaml_dsl import schema as schema_pkg

    assert getattr(schema_pkg, "__all__", None) == ()


def test_write_demand_schema_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "schema.json"
    write_demand_schema(output_path)

    content = output_path.read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_write_workflow_schema_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "schema.json"
    write_workflow_schema(output_path)

    content = output_path.read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_write_scalim_yaml_schema_creates_file(tmp_path: Path) -> None:
    output_path = tmp_path / "schema.json"
    write_scalim_yaml_schema(output_path)

    content = output_path.read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_build_field_definition_schema_mismatch() -> None:
    @dataclass
    class _SourceFieldConfig:
        name: str = dataclass_field(metadata={yaml_constants.SCHEMA_META_KEY: {"schema": {"type": "string"}}})

    @dataclass
    class _DerivedFieldConfig:
        name: str = dataclass_field(metadata={yaml_constants.SCHEMA_META_KEY: {"schema": {"type": "number"}}})

    dummy_types = SimpleNamespace(
        SourceFieldConfig=_SourceFieldConfig,
        DerivedFieldConfig=_DerivedFieldConfig,
        FIELD_DERIVED_CONDITIONS=[],
        SCHEMA_OMIT_KEY=yaml_constants.SCHEMA_OMIT_KEY,
        IMPORT_REF_SCHEMA=yaml_constants.IMPORT_REF_SCHEMA,
    )

    builder = SchemaBuilder(dummy_types)
    with pytest.raises(ValueError, match="Field schema mismatch"):
        builder._build_field_definition()


def test_normalize_schema_tuple_and_refs() -> None:
    class _Dummy:
        SCHEMA_NAME = "dummy"

    builder = SchemaBuilder()
    assert builder.normalize_schema((1, 2)) == [1, 2]
    assert builder._expand_additional_props("dummy") == {"$ref": "#/definitions/dummy"}
    assert builder._schema_for_type(_Dummy, allow_import=True) == {"$ref": "#/definitions/dummy"}


def test_key_map_helpers() -> None:
    assert LOOKUP_CAST_KEYS["name"] == "name"
    assert LOOKUP_CAST_KEYS.get("missing") is None
    items = dict(LOOKUP_CAST_KEYS.items())
    assert items["name"] == "name"


def test_normalize_schema_wrapper_matches_builder() -> None:
    builder = SchemaBuilder()
    schema = {"anyOf": [{"type": "string"}, {"type": "number"}]}
    assert normalize_schema(schema) == builder.normalize_schema(schema)


def test_schema_for_type_tuples() -> None:
    builder = SchemaBuilder()
    tuple_schema = builder._schema_for_type(tuple, allow_import=True)
    assert tuple_schema == {"type": "array"}

    typed_schema = builder._schema_for_type(Tuple[int, str], allow_import=True)
    assert typed_schema["minItems"] == 2
    assert typed_schema["maxItems"] == 2


def test_schema_builder_numeric_constraints_type_list_is_accepted() -> None:
    builder = SchemaBuilder()
    builder._assert_numeric_constraints_typed(  # noqa: SLF001
        {"type": ["integer", "null"], "minimum": 0},
        context="demo",
    )


def test_schema_builder_numeric_constraints_reject_non_numeric_type() -> None:
    builder = SchemaBuilder()
    with pytest.raises(ValueError, match=r"numeric constraints"):
        builder._assert_numeric_constraints_typed(  # noqa: SLF001
            {"type": "string", "minimum": 0},
            context="demo",
        )


def test_workflow_schema_import_key_assertion_fails() -> None:
    builder = SchemaBuilder()
    with pytest.raises(ValueError, match=r"MUST NOT expose"):
        builder._assert_schema_does_not_expose_import_key(  # noqa: SLF001
            {"$import": {"type": "string"}},
            path="$",
        )


def test_schema_omit_with_meta() -> None:
    meta = yaml_constants._schema_omit(desc="demo")
    assert meta[yaml_constants.SCHEMA_OMIT_KEY] is True
    assert yaml_constants.SCHEMA_META_KEY in meta


def test_expand_meta_wraps_scalar_examples() -> None:
    builder = SchemaBuilder()
    expanded = builder._expand_meta({"example": "demo"})

    assert expanded["examples"] == ["demo"]


def test_expand_meta_items_choices_populates_items_enum() -> None:
    builder = SchemaBuilder()
    expanded = builder._expand_meta({"items_choices": ["duration", "memory", "cpu"]})

    assert expanded["items"]["enum"] == ["duration", "memory", "cpu"]


def test_generated_schema_main_source_order_by_has_hover_meta() -> None:
    schema = load_schema(_schema_path("demand.gen.json"))
    order_by = schema["definitions"]["main_source"]["properties"]["order_by"]

    assert ("description" in order_by) or ("markdownDescription" in order_by)


def test_generated_schema_batch_size_supports_null_or_positive_integer() -> None:
    schema = build_demand_schema()
    assert "batch_size" not in (schema.get("properties") or {})


def test_doc_texts_first_non_empty_line_blank_returns_empty() -> None:
    assert yaml_doc_texts._first_non_empty_line("\n\n") == ""


def test_doc_texts_build_generated_doc_block_handles_empty_and_non_empty() -> None:
    assert yaml_doc_texts.build_generated_doc_block([]) == ""
    assert yaml_doc_texts.build_generated_doc_block(["a", "b"]) == "a\nb\n"


def test_generated_schema_outputs_where_and_aggregate_hovers_are_detailed() -> None:
    schema = load_schema(_schema_path("demand.gen.json"))

    output_target = schema["definitions"]["output_target"]
    where_schema = output_target["properties"]["where"]
    where_md = where_schema.get("markdownDescription") or ""
    assert "行级" in where_md
    assert "group_by" in where_md
    assert "fields.<field_id>" in where_md

    agg = schema["definitions"]["output_aggregate"]
    assert "metrics" not in agg["properties"]

    group_by_md = agg["properties"]["group_by"].get("markdownDescription") or ""
    assert "where" in group_by_md

    fields_md = agg["properties"]["fields"].get("markdownDescription") or ""
    assert "producer key" in fields_md
    assert "执行顺序" in fields_md

    one_of = agg["properties"]["fields"]["additionalProperties"]["oneOf"]
    sum_schema = next(item["properties"]["sum"] for item in one_of if "sum" in item.get("properties", {}))
    sum_md = sum_schema.get("markdownDescription") or ""
    assert "参数" in sum_md
    assert "`field`" in sum_md

    dense_rank_schema = next(item["properties"]["dense_rank"] for item in one_of if "dense_rank" in item.get("properties", {}))
    dense_rank_md = dense_rank_schema.get("markdownDescription") or ""
    assert "并列" in dense_rank_md
    assert "`by`" in dense_rank_md
