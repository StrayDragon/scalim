import json
from decimal import Decimal
from fractions import Fraction

import pytest

from scalim.dsl.by_yaml.config_parsing.validator import (
    ConfigValidator,
    YamlValidationIssue,
    YamlValidationResult,
    attach_locations,
    build_yaml_location_index,
    lookup_yaml_location,
    validate_yaml_text,
    validate_yaml_text_json,
)


def test_yaml_validation_issue_as_dict_omits_none_locations() -> None:
    issue = YamlValidationIssue(path="a.b", message="msg")
    payload = issue.as_dict()
    assert payload["path"] == "a.b"
    assert payload["message"] == "msg"
    assert "line" not in payload
    assert "column" not in payload

    issue_with_loc = YamlValidationIssue(path="a.b", message="msg", line=2, column=3, suggestions=["x"])
    payload2 = issue_with_loc.as_dict()
    assert payload2["line"] == 2
    assert payload2["column"] == 3
    assert payload2["suggestions"] == ["x"]


def test_yaml_validation_result_as_dict() -> None:
    result = YamlValidationResult(ok=False, errors=[YamlValidationIssue(path="x", message="bad")], warnings=[])
    payload = result.as_dict()
    assert payload["ok"] is False
    assert payload["errors"][0]["path"] == "x"
    assert payload["warnings"] == []


def test_build_yaml_location_index_handles_empty_and_invalid() -> None:
    assert build_yaml_location_index("") == {}
    assert build_yaml_location_index("a: [") == {}


def test_build_yaml_location_index_records_mapping_and_sequence() -> None:
    yaml_text = "root:\n  items:\n    - a\n    - b\n"
    locations = build_yaml_location_index(yaml_text)
    assert locations[""] == (1, 1)
    assert locations["root"] == (1, 1)
    assert locations["root.items"] == (2, 3)
    assert locations["root.items.0"] == (3, 7)
    assert locations["root.items.1"] == (4, 7)


def test_lookup_yaml_location_falls_back_to_parents_and_root() -> None:
    yaml_text = "root:\n  items:\n    - a\n"
    locations = build_yaml_location_index(yaml_text)
    assert lookup_yaml_location("root.items.0.unknown", locations) == locations["root.items.0"]
    assert lookup_yaml_location("", locations) == locations[""]
    assert lookup_yaml_location("", {}) is None
    assert lookup_yaml_location("missing.path", locations) == locations[""]


def test_attach_locations_respects_existing_location_and_defaults() -> None:
    yaml_text = "root:\n  items:\n    - a\n"
    locations = build_yaml_location_index(yaml_text)

    assert attach_locations([], locations) == []

    issue = YamlValidationIssue(path="root.items.0", message="msg")
    attached = attach_locations([issue], locations)
    assert attached[0].line == 3
    assert attached[0].column == 7

    preserved = YamlValidationIssue(path="(root)", message="msg", line=9, column=10)
    attached2 = attach_locations([preserved], locations)
    assert attached2[0].line == 9
    assert attached2[0].column == 10

    no_default = attach_locations([YamlValidationIssue(path="nope", message="msg")], {}, default=None)
    assert no_default[0].line is None
    assert no_default[0].column is None

    with_default = attach_locations([YamlValidationIssue(path="nope", message="msg")], {}, default=(7, 8))
    assert with_default[0].line == 7
    assert with_default[0].column == 8

    normalized = attach_locations([YamlValidationIssue(path="↳ root.items", message="msg")], locations)
    assert normalized[0].line == 2
    assert normalized[0].column == 3

    root_issue = attach_locations([YamlValidationIssue(path="(root)", message="msg")], locations)
    assert root_issue[0].line == 1
    assert root_issue[0].column == 1

    empty_issue = attach_locations([YamlValidationIssue(path="", message="msg")], locations)
    assert empty_issue[0].line == 1
    assert empty_issue[0].column == 1


def test_validate_yaml_text_reports_parse_error_with_location() -> None:
    result = validate_yaml_text("name: [\n")
    assert result.ok is False
    assert len(result.errors) == 1
    issue = result.errors[0]
    assert issue.path == "(root)"
    assert issue.message.startswith("YAML parse error:")
    assert issue.line is not None
    assert issue.column is not None


def test_validate_yaml_text_handles_empty_doc() -> None:
    result = validate_yaml_text("")
    assert result.ok is False
    assert result.errors[0].message == "YAML document is empty"
    assert result.errors[0].line == 1
    assert result.errors[0].column == 1


def test_validate_yaml_text_minimal_valid_config_ok() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is True
    assert result.errors == []


def test_validate_yaml_text_rejects_invalid_batch_size() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "batch_size: 0",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is False
    assert any(issue.path == "batch_size" for issue in result.errors)


def test_validate_yaml_text_allows_null_batch_size() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "batch_size: null",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is True


def test_validate_yaml_text_allows_null_batch_size_with_jsonschema_enabled() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "batch_size: null",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text, enable_jsonschema_validation=True)
    assert result.ok is True


@pytest.mark.parametrize(
    "batch_size_line",
    [
        "batch_size: true",
        "batch_size: 1.5",
        "batch_size: abc",
    ],
)
def test_validate_yaml_text_rejects_invalid_batch_size_types(batch_size_line: str) -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            batch_size_line,
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is False
    assert any(issue.path == "batch_size" for issue in result.errors)


def test_validator_rejects_int_castable_non_int_batch_size_objects() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {},
    }
    validator = ConfigValidator()

    for raw in (Decimal("2"), Fraction(4, 2), Fraction(3, 2)):
        report = validator.validate_report(dict(config, batch_size=raw))
        assert any(issue.path == "batch_size" for issue in report.errors())


def test_validate_yaml_text_rejects_invalid_cache_mode() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources:",
            "  customers:",
            "    loader: tests.conftest.mock_loader",
            "    key: id",
            "    cache_mode: preload",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is False
    assert any(issue.path == "sources.customers.cache_mode" for issue in result.errors)


def test_validate_yaml_text_unknown_field_warning_vs_error() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "unknown_key: 1",
            "",
        ]
    )
    result = validate_yaml_text(yaml_text, strict_unknown_fields=False)
    assert result.ok is True
    assert result.errors == []
    assert result.warnings
    assert result.warnings[0].line is not None

    strict_result = validate_yaml_text(yaml_text, strict_unknown_fields=True)
    assert strict_result.ok is False
    assert strict_result.errors
    assert strict_result.warnings == []


def test_validate_yaml_text_rejects_reserved_field_id_builtin_conflict() -> None:
    yaml_text = "\n".join(
        [
            "name: demo",
            "main_source:",
            "  source_id: orders",
            "  loader: tests.conftest.mock_loader",
            "sources: {}",
            "fields:",
            "  sum:",
            '    compute: "1"',
            "",
        ]
    )
    result = validate_yaml_text(yaml_text)
    assert result.ok is False
    assert any(issue.path == "fields.sum" for issue in result.errors)


def test_config_validator_reports_jsonschema_missing_as_warning_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.by_yaml.config_parsing import validator as validator_module  # noqa: PLC0415

    monkeypatch.setattr(validator_module, "HAS_JSONSCHEMA", False, raising=True)
    monkeypatch.setattr(validator_module, "jsonschema", None, raising=True)

    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {},
    }
    report = ConfigValidator().validate_report(dict(config), enable_jsonschema_validation=True)
    warnings = report.warnings()
    assert warnings
    assert any(issue.path == "(schema)" and issue.severity == "warning" for issue in warnings)


def test_config_validator_reports_jsonschema_internal_error_as_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.dsl.by_yaml.config_parsing import validator as validator_module  # noqa: PLC0415

    class DummyJsonSchema:
        class ValidationError(Exception):
            pass

        @staticmethod
        def validate(_config: object, _schema: object) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(validator_module, "HAS_JSONSCHEMA", True, raising=True)
    monkeypatch.setattr(validator_module, "jsonschema", DummyJsonSchema, raising=True)

    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {},
    }
    report = ConfigValidator().validate_report(dict(config), enable_jsonschema_validation=True)
    warnings = report.warnings()
    assert warnings
    assert any("JSONSchema validation failed unexpectedly" in issue.message for issue in warnings)


def test_config_validator_jsonschema_validate_fn_hook_short_circuits() -> None:
    called = []

    def _validate_fn(_config: object, _schema: object) -> None:
        called.append("ok")

    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {},
    }

    report = ConfigValidator(jsonschema_validate_fn=_validate_fn).validate_report(
        dict(config),
        enable_jsonschema_validation=True,
    )
    assert called
    assert report.ok() is True


def test_validate_yaml_text_json_roundtrip() -> None:
    raw = validate_yaml_text_json("name: [\n")
    payload = json.loads(raw)
    assert payload["ok"] is False
    assert payload["errors"]
    assert payload["warnings"] == []


def test_private_helpers_location_and_error_paths() -> None:
    from scalim.dsl.by_yaml.config_parsing import validator as validator_module  # noqa: PLC0415

    locations = {"a": (9, 9)}
    validator_module._record_location(locations, ["a"], None)
    assert locations == {"a": (9, 9)}

    mark = type("Mark", (), {"line": 0, "column": 0})()
    validator_module._record_location(locations, ["a"], mark)
    assert locations == {"a": (9, 9)}

    validator_module._record_location(locations, ["b"], mark)
    assert locations["b"] == (1, 1)

    validator_module._index_yaml_node(None, [], locations)

    class DummyExc(Exception):
        pass

    assert validator_module._extract_yaml_error_location(DummyExc()) is None

    exc = DummyExc()
    exc.problem_mark = type("BadMark", (), {"line": "nope", "column": 1})()
    assert validator_module._extract_yaml_error_location(exc) is None
