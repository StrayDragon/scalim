from pathlib import Path

import scalim.dsl.by_yaml._internal.config_parsing.validator as validator_module
from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.schema_dsl.models import (
    BOOK_KEYS,
    BOOK_WRITE_DEFAULTS_KEYS,
    DEMAND_KEYS,
    OUTPUT_TARGET_KEYS,
    OUTPUT_TO_KEYS,
    OUTPUT_WRITE_KEYS,
    RESOURCES_KEYS,
)


def _validator() -> ConfigValidator:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema" / "demand.gen.json"
    return ConfigValidator(schema_path=str(schema_path))


def test_config_validator_rejects_import_only_output_target_shape() -> None:
    report = _validator().validate_report(
        {
            "name": "demo",
            "main_source": {
                "source_id": "orders",
                "loader": "tests.fixtures.mock_loaders.mock_loader",
            },
            "sources": {},
            "outputs": [{"$import": "common.outputs"}],
        },
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )

    errors = report.errors()
    assert errors != []
    assert any(issue.path == "outputs.0" and "Schema validation error" in issue.message for issue in errors)


def test_validator_sources_skip_import_and_cover_key_edge_cases() -> None:
    report = _validator().validate_report(
        {
            "name": "demo",
            "main_source": {
                "source_id": "orders",
                "loader": "",
                "retry": {"should_retry": "   "},
            },
            "sources": {
                "$import": "fragments.yaml",
                "s_key_none": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": None},
                "s_key_empty_list": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": []},
                "s_key_non_str": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": [1]},
                "s_key_blank": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": [""]},
                "s_key_bad_pat_list": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": ["bad-id"]},
                "s_key_bad_pat_str": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": "bad-id"},
            },
        },
        strict_unknown_fields=False,
        enable_jsonschema_validation=False,
    )

    errors = report.errors()
    messages = [issue.message for issue in errors]
    paths = [issue.path for issue in errors]

    assert all(not str(path).startswith("sources.$import") for path in paths)
    assert any("main_source.loader must not be empty" in msg for msg in messages)
    assert any(path == "main_source.retry" for path in paths)
    assert any("moved out of YAML mainline" in msg and "loader_retry=LoaderRetryPoliciesSpec" in msg for msg in messages)
    assert any("sources.s_key_none.key must be a non-empty field_id or field_id list" in msg for msg in messages)
    assert any("sources.s_key_empty_list.key must not be empty" in msg for msg in messages)
    assert any("sources.s_key_non_str.key.0 must be a string" in msg for msg in messages)
    assert any("sources.s_key_blank.key.0 must not be empty" in msg for msg in messages)
    assert any("sources.s_key_bad_pat_list.key.0 must match field_id pattern" in msg for msg in messages)
    assert any("sources.s_key_bad_pat_str.key must match field_id pattern" in msg for msg in messages)


def test_output_item_requires_unique_effective_display_names_sheet_mode_reads_include_header() -> None:
    config = {
        DEMAND_KEYS["resources"]: {
            RESOURCES_KEYS["books"]: {
                "report": {
                    BOOK_KEYS["write_defaults"]: {
                        BOOK_WRITE_DEFAULTS_KEYS["mode"]: "sheet",
                    }
                }
            }
        }
    }
    output_item = {
        OUTPUT_TARGET_KEYS["to"]: {
            OUTPUT_TO_KEYS["book"]: "report",
        },
        OUTPUT_TARGET_KEYS["write"]: {
            OUTPUT_WRITE_KEYS["header_fields_output_by"]: "name",
            OUTPUT_WRITE_KEYS["include_header"]: True,
        },
    }
    assert validator_module._output_item_requires_unique_effective_display_names(config, output_item) is True


def test_validator_strips_removed_output_write_workbook_fields_keeps_remaining_keys() -> None:
    validator = _validator()
    issues = []
    config = {
        "outputs": [
            {
                OUTPUT_TARGET_KEYS["to"]: {
                    OUTPUT_TO_KEYS["book"]: "report",
                },
                "write": {
                    "mode": "append",
                    OUTPUT_WRITE_KEYS["include_header"]: True,
                },
            }
        ]
    }
    cleaned = validator._error_and_strip_removed_output_write_workbook_fields(config, issues)  # noqa: SLF001
    assert cleaned["outputs"][0]["write"] == {OUTPUT_WRITE_KEYS["include_header"]: True}  # type: ignore[index]
    assert issues
