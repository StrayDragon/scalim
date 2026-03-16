from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Tuple
from types import SimpleNamespace

import pytest

from scalim.dsl.by_yaml.schema_dsl import constants as yaml_constants
from scalim.dsl.by_yaml.schema_dsl.builder import (
    SchemaBuilder,
    build_demand_schema,
    build_workflow_schema,
    load_schema,
    normalize_schema,
    schemas_equivalent,
    write_demand_schema,
    write_workflow_schema,
)
from scalim.dsl.by_yaml.schema_dsl.models import LOOKUP_CAST_KEYS
from scalim.dsl.by_yaml.schema_dsl import doc_texts as yaml_doc_texts


def _schema_path(name: str) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema" / name


def test_generator_matches_generated_file() -> None:
    generated = build_demand_schema()
    file_schema = load_schema(_schema_path("demand.gen.json"))

    assert schemas_equivalent(generated, file_schema)


def test_workflow_generator_matches_generated_file() -> None:
    generated = build_workflow_schema()
    file_schema = load_schema(_schema_path("workflow.gen.json"))

    assert schemas_equivalent(generated, file_schema)


def test_generated_schema_has_comment() -> None:
    generated = load_schema(_schema_path("demand.gen.json"))

    assert "$comment" in generated


def test_generated_workflow_schema_has_comment() -> None:
    generated = load_schema(_schema_path("workflow.gen.json"))

    assert "$comment" in generated


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
    assert builder._schema_for_type(_Dummy) == {"$ref": "#/definitions/dummy"}


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
    tuple_schema = builder._schema_for_type(tuple)
    assert tuple_schema == {"type": "array"}

    typed_schema = builder._schema_for_type(Tuple[int, str])
    assert typed_schema["minItems"] == 2
    assert typed_schema["maxItems"] == 2


def test_schema_omit_with_meta() -> None:
    meta = yaml_constants._schema_omit(desc="demo")
    assert meta[yaml_constants.SCHEMA_OMIT_KEY] is True
    assert yaml_constants.SCHEMA_META_KEY in meta


def test_expand_meta_wraps_scalar_examples() -> None:
    builder = SchemaBuilder()
    expanded = builder._expand_meta({"example": "demo"})

    assert expanded["examples"] == ["demo"]


def test_observability_logging_schema_has_renderer_enum() -> None:
    schema = build_demand_schema()
    logging_schema = schema["definitions"]["logging"]
    renderer = logging_schema["properties"]["renderer"]

    assert renderer["type"] == "string"
    assert set(renderer["enum"]) == {"logger", "pretty"}


def test_generated_schema_main_source_order_by_has_hover_meta() -> None:
    schema = load_schema(_schema_path("demand.gen.json"))
    order_by = schema["definitions"]["main_source"]["properties"]["order_by"]

    assert ("description" in order_by) or ("markdownDescription" in order_by)


def test_generated_schema_batch_size_supports_null_or_positive_integer() -> None:
    schema = build_demand_schema()
    batch_size = schema["properties"]["batch_size"]

    one_of = batch_size["oneOf"]
    assert {"type": "null"} in one_of
    assert {"type": "integer", "minimum": 1} in one_of


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
