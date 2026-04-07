# pragma: allow-cast-file tests cover internal helpers; a few casts may be needed for patching/mocking
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from scalim.dsl.yaml_dsl.schema_dsl import builder as schema_builder
from scalim.dsl.yaml_dsl.schema_dsl import doc_standardizer as ds


def test_schema_doc_fixture_paths_skip_missing_files() -> None:
    original = schema_builder._SCHEMA_DOC_FIXTURE_RELATIVE_PATHS
    try:
        schema_builder._SCHEMA_DOC_FIXTURE_RELATIVE_PATHS = (
            "notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/does_not_exist.yaml",
            *original,
        )
        resolved = schema_builder._resolve_schema_doc_fixture_paths()
        assert all("does_not_exist.yaml" not in p for p in resolved)
    finally:
        schema_builder._SCHEMA_DOC_FIXTURE_RELATIVE_PATHS = original


def test_doc_standardizer_helper_edge_cases() -> None:
    assert ds._first_non_empty_line("") == ""

    original_safe_dump = ds.yaml.safe_dump

    def fake_safe_dump(*_args: Any, **_kwargs: Any) -> str:
        return "..."

    try:
        ds.yaml.safe_dump = fake_safe_dump  # type: ignore[assignment]
        assert ds._yaml_dump({"x": 1}) == "\n"
    finally:
        ds.yaml.safe_dump = original_safe_dump  # type: ignore[assignment]


def test_import_workaround_detection_failure_modes() -> None:
    assert ds._detect_import_required_workaround({"anyOf": ["x", {"required": ["$import"]}]}) is None
    assert ds._detect_import_required_workaround({"anyOf": [{"required": [1]}, {"required": ["$import"]}]}) is None
    assert ds._detect_import_required_workaround({"anyOf": [{"required": ["a"]}, {"required": ["b"]}]}) is None
    assert ds._detect_import_required_workaround({"anyOf": [{"required": ["$import"]}, {"required": ["$import"]}]}) is None


def test_schema_union_wrapper_edge_cases() -> None:
    assert ds._is_allof_ref_wrapper({"allOf": ["x"]}) is False
    assert ds._is_nullable_oneof({"oneOf": [{"type": "null"}, "x"]}) is False


def test_constraints_summary_branch_coverage() -> None:
    assert ds._build_constraints_summary({}, required=None, parent_has_import_workaround=False, referenced_schema=None) == ["- (无)"]

    lines = ds._build_constraints_summary({"const": 1}, required=None, parent_has_import_workaround=False, referenced_schema=None)
    assert any("const" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"items": {"type": "string"}}, required=None, parent_has_import_workaround=False, referenced_schema=None
    )
    assert any("items:" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"items": {"enum": ["a"]}}, required=None, parent_has_import_workaround=False, referenced_schema=None
    )
    assert any("items.取值" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"items": [{"type": "string"}]}, required=None, parent_has_import_workaround=False, referenced_schema=None
    )
    assert any("tuple" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"additionalProperties": True}, required=None, parent_has_import_workaround=False, referenced_schema=None
    )
    assert any("additionalProperties: true" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"anyOf": [{"required": ["a"]}, {"required": ["$import"]}]},
        required=None,
        parent_has_import_workaround=False,
        referenced_schema=None,
    )
    assert any("required:" in x for x in lines)

    lines = ds._build_constraints_summary(
        {"anyOf": [{"required": []}, {"required": ["$import"]}]}, required=None, parent_has_import_workaround=False, referenced_schema=None
    )
    assert any("仅" in x and "$import" in x for x in lines)


def test_minimal_schema_valid_value_branch_coverage() -> None:
    assert ds._build_minimal_schema_valid_value({"const": "x"}) == "x"

    assert ds._build_minimal_schema_valid_value({"oneOf": ["x"], "type": "string"}) == "demo"
    assert ds._build_minimal_schema_valid_value({"oneOf": [{"type": "null"}, {"type": "string"}]}) == "demo"
    assert (
        ds._build_minimal_schema_valid_value(
            {
                "oneOf": [
                    {"type": "string"},
                    {"properties": {"a": {"type": "string"}}},
                ],
            }
        )
        == "demo"
    )
    assert ds._build_minimal_schema_valid_value({"oneOf": [{"type": "string"}, {"$ref": "#/definitions/X"}]}) == "demo"
    assert ds._build_minimal_schema_valid_value({"oneOf": [{"type": "string"}, {"const": "x"}]}) == "demo"

    assert ds._build_minimal_schema_valid_value({"type": "null"}) is None

    assert ds._build_minimal_schema_valid_value({"type": "integer", "minimum": 5}) == 5
    assert ds._build_minimal_schema_valid_value({"type": "integer"}) == 0

    assert ds._build_minimal_schema_valid_value({"type": "number"}) == 0.0
    assert ds._build_minimal_schema_valid_value({"type": "boolean"}) is True

    assert ds._build_minimal_schema_valid_value({"type": "array", "minItems": 2, "items": {"type": "string"}}) == ["demo", "demo"]
    assert ds._build_minimal_schema_valid_value({"type": "array", "items": {"type": "string"}}) == []

    assert ds._build_minimal_schema_valid_value(
        {
            "type": "object",
            "anyOf": [{"required": []}, {"required": ["$import"]}],
            "properties": {"$import": {"type": "string"}},
        }
    ) == {"$import": "common.demo"}

    assert ds._build_minimal_schema_valid_value(
        {
            "type": "object",
            "anyOf": [{"required": ["a"]}, {"required": ["$import"]}],
            "properties": {"a": {"type": "string"}},
        }
    ) == {"$import": "common.demo"}

    assert ds._build_minimal_schema_valid_value({"type": "unknown"}) is None


def test_enum_semantics_validator_error_paths() -> None:
    ds._ensure_enum_semantics_markdown("x", [], node_path="p")

    with pytest.raises(ValueError):
        ds._ensure_enum_semantics_markdown("- `a`: ok", ["a", "b"], node_path="p")

    with pytest.raises(ValueError):
        ds._ensure_enum_semantics_markdown("- `a`\n- `b`: ok", ["a", "b"], node_path="p")


def test_standardize_schema_docs_and_definition_walk_edge_cases(tmp_path: Path) -> None:
    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "root_non_dict": "x",
            "arr": {"type": "array", "items": ["x"]},
            "obj": {
                "type": "object",
                "properties": {"a": "x"},
                "definitions": {"bad": "x", "ok": {}},
            },
        },
        "definitions": {"bad": "x"},
    }
    assert ds.standardize_schema_docs(schema, fixture_paths=()) is schema

    assert ds._infer_definition_roots(schema, definitions={}) == {}
    assert ds._longest_common_suffix_path([]) == ""
    assert ds._build_snippet_index(()) == {}

    _ = ds._collect_definition_reference_paths({"type": "array", "items": ["x"], "properties": {"a": "x"}}, definitions={})

    bad_end = tmp_path / "bad_end.yaml"
    bad_end.write_text(
        "\n".join(
            [
                "# <!-- BEGIN AUTOGEN:a -->",
                "x: 1",
                "# <!-- END AUTOGEN:b -->",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ds._extract_snippets_from_fixture(str(bad_end))

    unterminated = tmp_path / "unterminated.yaml"
    unterminated.write_text(
        "\n".join(
            [
                "# <!-- BEGIN AUTOGEN:a -->",
                "x: 1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ds._extract_snippets_from_fixture(str(unterminated))
