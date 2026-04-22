from pathlib import Path

import pytest

import scalim.dsl.yaml_dsl._internal.config_parsing.validator as validator_module
from scalim.dsl.yaml_dsl import CaptureRows, DemandRunOptions, DemandRunOutputOptions, DemandRunSecurityOptions, run
from scalim.dsl.yaml_dsl._internal.config_parsing.parsers.sources import ParserSourcesMixin
from scalim.dsl.yaml_dsl._internal.config_parsing.validators.sources import ValidatorSourcesMixin

import tests.fixtures.source_normalize_loaders as loaders


def _write_yaml(tmp_path: Path, text: str) -> Path:
    yaml_path = tmp_path / "normalize.yaml"
    yaml_path.write_text(text.strip() + "\n", encoding="utf-8")
    return yaml_path


def _assert_validation_errors(config: dict, *expected_messages: str) -> None:
    validator = validator_module.ConfigValidator()
    with pytest.raises(validator_module.ScalimConfigValidationError) as exc:
        validator.validate(config)
    errors = exc.value.errors
    for message in expected_messages:
        assert any(message in msg for msg in errors)


def _validate_normalize_raw(normalize_raw: object, *, key_raw: object = "id") -> list:
    validator = ValidatorSourcesMixin()
    errors: list = []
    validator._validate_normalize(  # type: ignore[attr-defined]
        normalize_raw,
        errors,
        path_prefix="sources.s1",
        source_id="s1",
        key_raw=key_raw,
    )
    return errors


def test_validator_rejects_main_source_normalize() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.source_normalize_loaders:load_orders_main",
            "normalize": {"kind": "index_by_key", "key_field": "order_id"},
        },
        "sources": {},
    }
    _assert_validation_errors(config, "main_source.normalize")


def test_validator_allows_omitting_normalize_key_field_defaults_to_key() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.source_normalize_loaders:load_orders_main",
            "fields": {"order_id": {"extract": "order_id"}},
        },
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key"},
            }
        },
    }
    validator = validator_module.ConfigValidator()
    validator.validate(config)


def test_validator_requires_normalize_to_be_mapping() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": "bad",
            }
        },
    }
    _assert_validation_errors(config, "normalize' must be a dictionary")


def test_validator_rejects_unknown_normalize_kind() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "bad", "key_field": "order_id"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.kind must be one of: index_by_key/take_first/project_fields/map_values")


def test_validator_rejects_normalize_for_composite_key() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": ["region_id", "institution_id"],
                "normalize": {"kind": "index_by_key", "key_field": "region_id"},
            }
        },
    }
    _assert_validation_errors(config, "does not support composite key yet")


def test_validator_rejects_normalize_key_field_mismatch() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key", "key_field": "other"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.key_field must equal sources")


def test_validator_rejects_non_string_normalize_key_field() -> None:
    errors = _validate_normalize_raw({"kind": "index_by_key", "key_field": 123}, key_raw="id")
    assert any("normalize.key_field must be a string" in issue.message for issue in errors)


def test_validator_rejects_normalize_on_conflict_invalid() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key", "key_field": "order_id", "on_conflict": "bad"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.on_conflict must be one of")


def test_validator_rejects_normalize_on_none_for_non_index_by_key() -> None:
    errors = _validate_normalize_raw({"kind": "take_first", "on_none": "skip"})
    assert any("normalize.on_none is only supported for normalize.kind=index_by_key" in issue.message for issue in errors)


def test_validator_rejects_normalize_on_none_invalid() -> None:
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.source_normalize_loaders:load_orders_main"},
        "sources": {
            "recommends": {
                "loader": "tests.fixtures.source_normalize_loaders:load_recommends_list",
                "key": "order_id",
                "normalize": {"kind": "index_by_key", "key_field": "order_id", "on_none": "bad"},
            }
        },
    }
    _assert_validation_errors(config, "normalize.on_none must be one of: raise/skip")


def test_run_applies_normalize_index_by_key_before_extract(tmp_path: Path) -> None:
    loaders.reset_call_counts()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_non_cached
main_source:
  source_id: orders
  loader: tests.fixtures.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.fixtures.source_normalize_loaders:load_recommends_list
    key: order_id
    normalize:
      kind: index_by_key
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id
""",
    )

    result = run(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"])),
            outputs=DemandRunOutputOptions(capture=CaptureRows()),
        ),
    )

    assert result.captured_rows is not None
    rows = list(result.captured_rows.iter_row_data())
    by_order_id = {row["order_id"]: row for row in rows}
    assert by_order_id[101]["recommend_score"] == 0.9
    assert by_order_id[102]["recommend_score"] == 0.7
    assert loaders.CALL_COUNTS["recommends"] >= 1


def test_run_normalize_index_by_key_on_none_skip(tmp_path: Path) -> None:
    loaders.reset_call_counts()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_skip_none
main_source:
  source_id: orders
  loader: tests.fixtures.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.fixtures.source_normalize_loaders:load_recommends_list_with_none_key
    key: order_id
    normalize:
      kind: index_by_key
      on_none: skip
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id
""",
    )

    result = run(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"])),
            outputs=DemandRunOutputOptions(capture=CaptureRows()),
        ),
    )

    assert result.captured_rows is not None
    rows = list(result.captured_rows.iter_row_data())
    by_order_id = {row["order_id"]: row for row in rows}
    assert by_order_id[101]["recommend_score"] == 0.9
    assert by_order_id[102]["recommend_score"] == 0.7


def test_run_preload_forever_caches_normalized_mapping(tmp_path: Path) -> None:
    loaders.reset_call_counts()
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_preload
main_source:
  source_id: orders
  loader: tests.fixtures.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.fixtures.source_normalize_loaders:load_recommends_list
    key: order_id
    cache_mode: preload_forever
    normalize:
      kind: index_by_key
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id
""",
    )

    result = run(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"])),
            outputs=DemandRunOutputOptions(capture=CaptureRows()),
        ),
    )

    assert result.captured_rows is not None
    rows = list(result.captured_rows.iter_row_data())
    by_order_id = {row["order_id"]: row for row in rows}
    assert by_order_id[101]["recommend_score"] == 0.9
    assert by_order_id[102]["recommend_score"] == 0.7
    assert loaders.CALL_COUNTS["recommends"] == 1


def test_run_rejects_normalize_call_by_not_in_allowlist(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimAllowlistViolationError

    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_call_by_not_allowed
main_source:
  source_id: orders
  loader: tests.fixtures.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.fixtures.source_normalize_loaders:load_recommends_list
    key: order_id
    normalize:
      kind: index_by_key
      key_field: order_id
      call_by: tests.fixtures.source_normalize_call_by:normalize_identity
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id
    """,
    )

    with pytest.raises(ScalimAllowlistViolationError, match=r"source_normalize_call_by.*allowed_modules"):
        _ = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders"]))
            ),
        )


def test_run_rejects_normalize_call_by_return_non_mapping(tmp_path: Path) -> None:
    yaml_path = _write_yaml(
        tmp_path,
        """
name: normalize_call_by_bad_return
main_source:
  source_id: orders
  loader: tests.fixtures.source_normalize_loaders:load_orders_main
  fields:
    order_id:
      extract: order_id

sources:
  recommends:
    loader: tests.fixtures.source_normalize_loaders:load_recommends_list
    key: order_id
    normalize:
      kind: index_by_key
      key_field: order_id
      call_by: tests.fixtures.source_normalize_call_by:normalize_bad_return
    fields:
      recommend_score:
        extract: payload.score
        relation:
          steps:
            - from: orders.order_id
              to: recommends.order_id
""",
    )

    with pytest.raises(TypeError, match=r"must return Mapping.*sources\.recommends\.normalize\.call_by"):
        _ = run(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(
                    allowed_modules=frozenset(["tests.fixtures.source_normalize_loaders", "tests.fixtures.source_normalize_call_by"])
                )
            ),
        )


def test_converter_rejects_unknown_normalize_kind() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="bad", key_field="id"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.kind must be one of: index_by_key/take_first/project_fields/map_values"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_defaults_normalize_key_field_to_source_key() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field=""),
    )
    ir = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]
    assert ir is not None
    assert ir.key_field == "id"


def test_converter_rejects_empty_source_key_for_index_by_key_normalize() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="",
        normalize=NormalizeConfig(kind="index_by_key", key_field=""),
    )
    with pytest.raises(ScalimConversionError, match=r"sources\.s1\.key must be a non-empty string"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_invalid_normalize_on_conflict() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="id", on_conflict="bad"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.on_conflict must be one of"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_invalid_normalize_on_none() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="id", on_none="bad"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.on_none must be one of"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_normalize_for_composite_key() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key=("a", "b"),
        normalize=NormalizeConfig(kind="index_by_key", key_field="a"),
    )
    with pytest.raises(ScalimConversionError, match="does not support composite key yet"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_normalize_key_field_mismatch() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="other"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.key_field must equal sources\\.s1\\.key"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_parser_sources_normalize_helpers_cover_skip_branches() -> None:
    class _Parser(ParserSourcesMixin):
        pass

    parser = _Parser()
    _ = parser._parse_normalize_project_fields({"": {"from_key": True}, "x": {"from_key": True}, "y": "not-a-dict"})  # type: ignore[attr-defined]
    _ = parser._parse_normalize_steps(["not-a-dict", {"kind": "take_first"}])  # type: ignore[attr-defined]
    norm = parser._parse_normalize({"kind": "take_first", "on_empty": "miss", "on_missing": "null"})  # type: ignore[attr-defined]
    assert norm is not None


def test_parser_sources_lookup_cast_rejects_invalid_shapes() -> None:
    class _Parser(ParserSourcesMixin):
        pass

    parser = _Parser()

    with pytest.raises(TypeError, match="Legacy YAML syntax is not supported for lookup_cast"):
        _ = parser._parse_lookup_cast({"name": "int"})  # type: ignore[attr-defined]

    with pytest.raises(TypeError, match="lookup_cast must select exactly one branch"):
        _ = parser._parse_lookup_cast({"int": {}, "str": {}})  # type: ignore[attr-defined]

    with pytest.raises(TypeError, match=r"lookup_cast\.int must be a dictionary"):
        _ = parser._parse_lookup_cast({"int": 1})  # type: ignore[attr-defined]

    with pytest.raises(TypeError, match=r"lookup_cast\.int must be an empty object"):
        _ = parser._parse_lookup_cast({"int": {"x": 1}})  # type: ignore[attr-defined]


def test_validator_sources_normalize_call_by_validation_branches() -> None:
    errors = _validate_normalize_raw({"kind": "index_by_key", "key_field": "id", "call_by": 123})
    assert any("normalize.call_by must be a string" in issue.message for issue in errors)

    errors = _validate_normalize_raw({"kind": "index_by_key", "key_field": "id", "call_by": "  "})
    assert any("normalize.call_by must not be empty" in issue.message for issue in errors)

    errors = _validate_normalize_raw({"kind": "index_by_key", "key_field": "id", "call_by": "bad ref"})
    assert any("normalize.call_by 引用" in issue.message for issue in errors)


def test_validator_sources_normalize_take_first_and_project_fields_branch_coverage() -> None:
    errors = _validate_normalize_raw(
        {
            "kind": "take_first",
            "key_field": "id",
            "on_conflict": "error",
            "on_missing": "error",
            "fields": {},
            "steps": [],
            "on_empty": "bad",
        }
    )
    assert errors

    errors = _validate_normalize_raw({"kind": "take_first"})
    assert errors == []

    errors = _validate_normalize_raw(
        {
            "kind": "project_fields",
            "key_field": "id",
            "on_conflict": "error",
            "on_none": "skip",
            "on_empty": "miss",
            "steps": [],
            "on_missing": "bad",
        }
    )
    assert errors

    errors = _validate_normalize_raw({"kind": "project_fields", "on_missing": "bad", "fields": "not-a-dict"})
    assert errors


def test_validator_sources_normalize_map_values_branch_coverage() -> None:
    errors = _validate_normalize_raw({"kind": "map_values", "steps": "not-a-list"})
    assert errors

    errors = _validate_normalize_raw({"kind": "map_values", "steps": []})
    assert errors

    errors = _validate_normalize_raw(
        {
            "kind": "map_values",
            "key_field": "id",
            "on_conflict": "error",
            "on_none": "skip",
            "on_empty": "miss",
            "on_missing": "error",
            "fields": {},
            "steps": [
                "not-a-dict",
                {"call_by": "x"},
                {},
                {"kind": 123},
                {"kind": "bad"},
                {"kind": "take_first", "fields": {}, "on_missing": "error", "key_field": "id", "on_conflict": "error"},
                {"kind": "take_first", "on_empty": "bad"},
                {"kind": "project_fields", "on_empty": "miss", "key_field": "id", "on_conflict": "error", "on_missing": "bad"},
            ],
        }
    )
    assert errors

    validator = ValidatorSourcesMixin()
    rules_errors: list = []
    validator._validate_normalize_project_fields_rules(  # type: ignore[attr-defined]
        "not-a-dict",
        rules_errors,
        fields_path="sources.s1.normalize.fields",
    )
    validator._validate_normalize_project_fields_rules(  # type: ignore[attr-defined]
        {},
        rules_errors,
        fields_path="sources.s1.normalize.fields",
    )
    validator._validate_normalize_project_fields_rules(  # type: ignore[attr-defined]
        {
            "rule_raw_not_mapping": "bad",
            "both": {"from_key": True, "extract": "id"},
            "neither": {},
            "from_key_not_bool": {"from_key": "bad"},
            "extract_not_str": {"extract": 1},
            "extract_empty": {"extract": " "},
            "extract_invalid": {"extract": "[x"},
        },
        rules_errors,
        fields_path="sources.s1.normalize.fields",
    )
    assert rules_errors


def test_converter_converts_take_first_normalize() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="take_first", on_empty="null"),
    )
    ir = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]
    assert ir is not None
    assert ir.kind == "take_first"
    assert ir.on_empty == "null"


def test_converter_rejects_take_first_invalid_on_empty() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="take_first", on_empty="bad"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.on_empty must be one of: miss/null/error"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_normalize_call_by_empty() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="index_by_key", key_field="id", call_by=" "),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.call_by must not be empty"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_converts_project_fields_normalize() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, NormalizeProjectFieldRuleConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(
            kind="project_fields",
            on_missing="null",
            fields={
                "id": NormalizeProjectFieldRuleConfig(from_key=True),
                "review_status": NormalizeProjectFieldRuleConfig(extract="review_status"),
            },
        ),
    )
    ir = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]
    assert ir is not None
    assert ir.kind == "project_fields"
    assert ir.on_missing == "null"
    assert {rule.name for rule in ir.fields} == {"id", "review_status"}


def test_converter_rejects_project_fields_invalid_on_missing() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", on_missing="bad", fields={"id": {"from_key": True}}),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.on_missing must be one of: error/null"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_project_fields_empty_rules() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", fields={}),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.fields.*must not be empty"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_project_fields_invalid_rule_shapes() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, NormalizeProjectFieldRuleConfig, SourceConfig

    converter = ConfigToIRConverter()

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", fields={"x": object()}),
    )
    with pytest.raises(ScalimConversionError, match="must be a normalize project_fields rule"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", fields={"x": NormalizeProjectFieldRuleConfig(from_key=True, extract="id")}),
    )
    with pytest.raises(ScalimConversionError, match="must not declare both"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", fields={"x": NormalizeProjectFieldRuleConfig()}),
    )
    with pytest.raises(ScalimConversionError, match="must declare from_key or extract"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="project_fields", fields={"x": NormalizeProjectFieldRuleConfig(extract="[x")}),
    )
    with pytest.raises(ScalimConversionError, match="has invalid extract"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_map_values_empty_steps() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, SourceConfig

    converter = ConfigToIRConverter()
    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="map_values"),
    )
    with pytest.raises(ScalimConversionError, match="normalize\\.steps must not be empty"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]


def test_converter_rejects_map_values_step_invalid_configs() -> None:
    from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.yaml_dsl.runtime.errors import ScalimConversionError
    from scalim.dsl.yaml_dsl.schema_dsl.models import NormalizeConfig, NormalizeStepConfig, SourceConfig

    converter = ConfigToIRConverter()

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="map_values", steps=(NormalizeStepConfig(kind="take_first", on_empty="bad"),)),
    )
    with pytest.raises(ScalimConversionError, match="on_empty must be one of: miss/null/error"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="map_values", steps=(NormalizeStepConfig(kind="project_fields", on_missing="bad"),)),
    )
    with pytest.raises(ScalimConversionError, match="on_missing must be one of: error/null"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]

    source_config = SourceConfig(
        source_id="s1",
        loader="tests.fixtures.mock_loaders.mock_loader",
        key="id",
        normalize=NormalizeConfig(kind="map_values", steps=(NormalizeStepConfig(kind="bad"),)),
    )
    with pytest.raises(ScalimConversionError, match="kind must be one of: take_first/project_fields"):
        _ = converter._convert_source_normalize(source_config)  # type: ignore[attr-defined]
