import pytest

import scalim.dsl.yaml_dsl._internal.config_parsing.validator as validator_module
from scalim.dsl.yaml_dsl._internal.config_parsing.parsers.fields import ParserFieldsMixin


def _minimal_ref_default_config(*, default_case: object, extra_fields: object = None) -> dict:
    cfg = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders:mock_loader",
            "fields": {
                "cs_id": {"extract": "cs_id"},
            },
        },
        "sources": {
            "cs": {
                "loader": "tests.fixtures.mock_loaders:mock_loader",
                "key": "cs_id",
                "fields": {
                    "metric": {
                        "extract": "metric",
                        "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
                        "default": [default_case],
                    }
                },
            }
        },
    }
    if extra_fields is not None:
        cfg["sources"]["cs"]["fields"].update(extra_fields)  # type: ignore[index]
    return cfg


def _assert_validation_error(config: dict, *expected_messages: str) -> None:
    validator = validator_module.ConfigValidator()
    with pytest.raises(validator_module.ScalimConfigValidationError) as exc:
        validator.validate(config)
    errors = exc.value.errors
    for message in expected_messages:
        assert any(message in msg for msg in errors)


def test_validator_accepts_ref_default_literal_case() -> None:
    validator = validator_module.ConfigValidator()
    report = validator.validate_report(
        _minimal_ref_default_config(default_case={"when": "relation_miss", "literal": 0}),
        strict_unknown_fields=True,
    )
    assert report.errors() == []


def test_validator_rejects_default_on_non_ref_field() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders:mock_loader",
            "fields": {
                "cs_id": {
                    "extract": "cs_id",
                    "default": [{"when": "relation_miss", "literal": 0}],
                }
            },
        },
        "sources": {},
    }
    _assert_validation_error(config, "default is only allowed for ref fields")


def test_validator_rejects_default_case_oneof_violation() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(
            default_case={
                "when": "relation_miss",
                "literal": 0,
                "call_by": "^defaults/zero_of_value_cast()",
            }
        ),
        "must declare exactly one of: literal/call_by",
    )


def test_validator_rejects_default_case_unknown_when() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(default_case={"when": "hit_null", "literal": 0}),
        "unsupported when",
    )


def test_validator_rejects_default_case_call_by_missing_parentheses() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(default_case={"when": "relation_miss", "call_by": "^defaults/zero_of_value_cast"}),
        "invalid call_by",
    )


def test_validator_rejects_default_call_by_dependency_on_ref_field() -> None:
    config = _minimal_ref_default_config(
        default_case={"when": "relation_miss", "call_by": "tests.fixtures.mock_loaders:mock_loader(dep=dept_name)"},
        extra_fields={
            "dept_name": {
                "extract": "dept_name",
                "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
            }
        },
    )
    _assert_validation_error(config, "default.call_by depends on 'dept_name' which is not pre-ref computable")


class _Parser(ParserFieldsMixin):
    pass


def test_parser_source_field_default_parses_list_of_objects() -> None:
    parser = _Parser()
    field = parser._parse_source_field(
        "metric",
        {
            "extract": "metric",
            "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
            "default": [{"when": "relation_miss", "literal": 0}],
        },
        source_id="cs",
        relations={},
    )
    assert field.default is not None
    assert field.default == ({"when": "relation_miss", "literal": 0},)


def test_parser_source_field_default_rejects_non_list() -> None:
    parser = _Parser()
    with pytest.raises(TypeError, match=r"default must be a list"):
        _ = parser._parse_source_field(
            "metric",
            {
                "extract": "metric",
                "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
                "default": {"when": "relation_miss", "literal": 0},
            },
            source_id="cs",
            relations={},
        )


def test_parser_source_field_default_rejects_non_object_items() -> None:
    parser = _Parser()
    with pytest.raises(TypeError, match=r"default\[0\] must be an object"):
        _ = parser._parse_source_field(
            "metric",
            {
                "extract": "metric",
                "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
                "default": [123],
            },
            source_id="cs",
            relations={},
        )


def test_validator_source_field_default_cases_is_noop_when_default_missing() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    validator._validate_source_field_default_cases(  # type: ignore[attr-defined] internal method coverage
        field_id="metric",
        field_data={},
        relation_val={},
        errors=errors,
        field_path="sources.cs.fields.metric",
    )
    assert errors == []


def test_validator_rejects_default_not_list() -> None:
    config = _minimal_ref_default_config(default_case={"when": "relation_miss", "literal": 0})
    config["sources"]["cs"]["fields"]["metric"]["default"] = {}  # type: ignore[index]
    _assert_validation_error(config, "default must be a list")


def test_validator_rejects_default_empty_list() -> None:
    config = _minimal_ref_default_config(default_case={"when": "relation_miss", "literal": 0})
    config["sources"]["cs"]["fields"]["metric"]["default"] = []  # type: ignore[index]
    _assert_validation_error(config, "default must not be empty")


def test_validator_rejects_default_case_not_object() -> None:
    config = _minimal_ref_default_config(default_case={"when": "relation_miss", "literal": 0})
    config["sources"]["cs"]["fields"]["metric"]["default"] = [123]  # type: ignore[index]
    _assert_validation_error(config, "default[0] must be an object")


def test_validator_rejects_default_case_missing_when() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(default_case={"literal": 0}),
        "missing required 'when'",
    )


def test_validator_rejects_default_case_literal_not_yaml_scalar() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(default_case={"when": "relation_miss", "literal": {"x": 1}}),
        "literal must be a YAML scalar",
    )


def test_validator_rejects_default_case_call_by_not_string() -> None:
    _assert_validation_error(
        _minimal_ref_default_config(default_case={"when": "relation_miss", "call_by": ""}),
        "call_by must be a non-empty string",
    )


def test_validator_default_call_by_dependency_on_main_source_non_ref_is_allowed() -> None:
    validator = validator_module.ConfigValidator()
    report = validator.validate_report(
        _minimal_ref_default_config(
            default_case={"when": "relation_miss", "call_by": "tests.fixtures.mock_loaders:mock_loader(dep=cs_id)"}
        ),
        strict_unknown_fields=True,
    )
    assert report.errors() == []


def test_validator_default_call_by_dependency_on_derived_field_reports_kind() -> None:
    config = _minimal_ref_default_config(
        default_case={"when": "relation_miss", "call_by": "tests.fixtures.mock_loaders:mock_loader(dep=bad_derived)"}
    )
    config["fields"] = {  # type: ignore[assignment]
        "bad_derived": {
            "compute": "dept_name",
        }
    }
    config["sources"]["cs"]["fields"]["dept_name"] = {  # type: ignore[index]
        "extract": "dept_name",
        "relation": {"steps": [{"from": "orders.cs_id", "to": "cs.cs_id"}]},
    }
    _assert_validation_error(config, "kind=derived")


def test_validator_default_call_by_dependency_on_unknown_field_is_rejected() -> None:
    config = _minimal_ref_default_config(
        default_case={
            "when": "relation_miss",
            "call_by": "tests.fixtures.mock_loaders:mock_loader(dep=unknown_field)",
        }
    )
    _assert_validation_error(config, "default.call_by depends on 'unknown_field' which is not pre-ref computable")
