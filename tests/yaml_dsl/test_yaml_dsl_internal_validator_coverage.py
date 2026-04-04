from pathlib import Path

from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime import effective_outputs as effective_outputs_mod
from scalim.dsl.by_yaml.schema_dsl.models import (
    OUTPUT_TARGET_KEYS,
    OUTPUT_TO_KEYS,
    OUTPUT_WRITE_KEYS,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
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
    loader = YamlDemandLoader()
    config = loader.load_string(
        """
name: validator_unique_sheet_mode
main_source:
  source_id: orders
  loader: tests.fixtures.mock_loaders.mock_loader
  fields:
    order_id: {extract: order_id}
sources: {}
resources:
  books:
    report:
      kind: xlsx_file
      path: ./out.xlsx
      write_defaults:
        mode: sheet
""",
    )
    out_cfg = OutputTargetConfig(
        name="detail",
        to=OutputToConfig(book="report", sheet="S"),
        write=OutputWriteConfig(header_fields_output_by="name", include_header=True),
        fields=("order_id",),
    )
    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(config, out_cfg, resources_override=None) is True
    )


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
