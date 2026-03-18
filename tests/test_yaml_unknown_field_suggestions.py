from pathlib import Path

from scalim.dsl.by_yaml.config_parsing.unknown_fields import find_unknown_fields
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator


def test_find_unknown_fields_reports_paths_and_suggestions() -> None:
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "items": {"type": "array"},
            "main_source": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "loader": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "sources": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "loader": {"type": "string"},
                        "key": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
            },
            "empty": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }

    yaml_data = {
        "name": "demo",
        "items": [{"x": 1}, 2],
        "main_source": {
            "_comment": "ignored",
            "sorce_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {
            "orders": {
                "loade": "tests.conftest.mock_loader",
                "key": "order_id",
            }
        },
        "empty": {"x": 1},
    }

    issues = find_unknown_fields(yaml_data, schema)
    by_path = {issue.path: issue for issue in issues}

    assert "main_source._comment" not in by_path

    assert by_path["main_source.sorce_id"].suggestions == ("source_id",)
    assert by_path["sources.orders.loade"].suggestions == ("loader",)
    assert by_path["empty.x"].suggestions == ()


def test_find_unknown_fields_traverses_array_items_and_oneof_branch() -> None:
    schema = {
        "type": "object",
        "properties": {
            "outputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "container": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "path": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {"$init_var": {"type": "string"}},
                                            "additionalProperties": False,
                                        },
                                    ]
                                },
                            },
                            "additionalProperties": False,
                        }
                    },
                    "additionalProperties": False,
                },
            }
        },
        "additionalProperties": False,
    }

    yaml_data = {
        "outputs": [
            {
                "container": {
                    "type": "workbook",
                    "path": {"$init_var": "out_path", "other": 1},
                    "unknown_field": 1,
                }
            }
        ]
    }

    issues = find_unknown_fields(yaml_data, schema)
    paths = {issue.path for issue in issues}
    assert "outputs.0.container.unknown_field" in paths
    assert "outputs.0.container.path.other" in paths


def test_find_unknown_fields_returns_empty_for_unknown_schema_shape() -> None:
    assert find_unknown_fields([], {}) == []
    assert find_unknown_fields({"a": 1}, {"type": "object"}) == []


def test_validator_unknown_field_suggestions_warning_vs_error() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.conftest.mock_loader",
        },
        "sources": {},
        "fields": {
            "profit": {
                "compute": "1",
                "commpute": "2",
            }
        },
    }

    validator = ConfigValidator()

    report = validator.validate_report(config)
    assert report.ok()
    assert [issue.path for issue in report.errors()] == []
    warnings = {issue.path: issue for issue in report.warnings()}
    assert warnings["fields.profit.commpute"].suggestions == ("compute",)

    strict_report = validator.validate_report(config, strict_unknown_fields=True)
    assert not strict_report.ok()
    errors = {issue.path: issue for issue in strict_report.errors()}
    assert errors["fields.profit.commpute"].suggestions == ("compute",)


def test_validator_skips_unknown_fields_when_schema_unloadable(tmp_path) -> None:
    schema_path = tmp_path / "bad-schema.json"
    schema_path.write_text("{ invalid json", encoding="utf-8")

    config = {"name": "demo", "main_source": {}, "sources": {}}
    validator = ConfigValidator(schema_path=str(schema_path))
    report = validator.validate_report(config)

    assert report.issues
    assert not any(issue.message.startswith("Unknown field") for issue in report.issues)


def test_find_unknown_fields_schema_ref_resolution_edge_cases() -> None:
    assert (
        find_unknown_fields(
            {"x": {"y": 1}},
            {"type": "object", "properties": {"x": {"$ref": "http://example.com/schema"}}},
        )
        == []
    )

    assert (
        find_unknown_fields(
            {"x": {"y": 1}},
            {"type": "object", "properties": {"x": {"$ref": "#/missing"}}},
        )
        == []
    )

    assert (
        find_unknown_fields(
            {"x": {"y": 1}},
            {"type": "object", "properties": {"x": {"$ref": "#/defs/x"}}, "defs": "not-a-dict"},
        )
        == []
    )

    definitions = {}
    for i in range(31):
        definitions["a{}".format(i)] = {"$ref": "#/definitions/a{}".format(i + 1)}
    definitions["a31"] = {}

    assert (
        find_unknown_fields({"x": {}}, {"type": "object", "properties": {"x": {"$ref": "#/definitions/a0"}}, "definitions": definitions})
        == []
    )

    assert (
        find_unknown_fields(
            {"x": {"y": 1}},
            {
                "type": "object",
                "properties": {"x": {"$ref": "#/definitions/loop"}},
                "definitions": {"loop": {"allOf": [{"$ref": "#/definitions/loop"}]}},
            },
        )
        == []
    )
