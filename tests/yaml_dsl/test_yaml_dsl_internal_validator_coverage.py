from pathlib import Path

from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl.runtime import effective_outputs as effective_outputs_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    OUTPUT_TARGET_KEYS,
    OUTPUT_TO_KEYS,
    OUTPUT_WRITE_KEYS,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)


def _validator() -> ConfigValidator:
    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "src" / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
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
    )

    errors = report.errors()
    assert errors != []
    assert any(issue.path == "outputs.0.$import" and "Unknown field" in issue.message for issue in errors)


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
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    path="./out",
                    write_defaults=BookWriteDefaultsConfig(mode="sheet"),
                ),
            }
        )
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


def test_validator_relations_accepts_none_and_source_field_group_empty_list() -> None:
    validator = _validator()
    errors = []

    out = validator._validate_relations(  # noqa: SLF001
        {"relations": None},
        errors,
        sources_info={},
        main_source_id="orders",
    )
    assert out == {}
    assert errors == []

    assert validator._parse_source_field_group([]) is None  # noqa: SLF001


def test_validator_field_relation_returns_when_steps_are_invalid() -> None:
    validator = _validator()
    errors = []
    validator._validate_field_relation(  # noqa: SLF001
        field_id="f",
        relation_val={"steps": None},
        source_id="s1",
        main_source_id="main",
        sources_set=set(["s1", "main"]),
        sources_info={},
        relation_paths={},
        errors=errors,
        field_path="sources.s1.fields.f",
    )
    assert errors


def test_validator_sources_normalize_options_cover_valid_branches() -> None:
    validator = _validator()
    errors = []
    validator._validate_normalize_take_first(  # noqa: SLF001
        {"on_empty": "miss"},
        errors,
        norm_path="sources.s1.normalize",
        source_id="s1",
    )
    assert errors == []

    errors = []
    validator._validate_normalize_project_fields(  # noqa: SLF001
        {"fields": {"v": {"extract": "a"}}},
        errors,
        norm_path="sources.s1.normalize",
        source_id="s1",
    )
    assert errors == []

    errors = []
    validator._validate_normalize_project_fields(  # noqa: SLF001
        {"on_missing": "null", "fields": {"v": {"extract": "a"}}},
        errors,
        norm_path="sources.s1.normalize",
        source_id="s1",
    )
    assert errors == []

    errors = []
    validator._validate_normalize_step_project_fields(  # noqa: SLF001
        {"fields": {"v": {"extract": "a"}}},
        errors,
        step_path="sources.s1.normalize.steps[0]",
    )
    assert errors == []


def test_validator_strips_removed_output_write_workbook_fields_multiple_outputs_reuses_next_config() -> None:
    validator = _validator()
    issues = []
    config = {
        "outputs": [
            {
                OUTPUT_TARGET_KEYS["to"]: {OUTPUT_TO_KEYS["book"]: "report"},
                "write": {
                    "mode": "append",
                    OUTPUT_WRITE_KEYS["include_header"]: True,
                },
            },
            {
                OUTPUT_TARGET_KEYS["to"]: {OUTPUT_TO_KEYS["book"]: "report"},
                "write": {
                    "mode": "append",
                    OUTPUT_WRITE_KEYS["include_header"]: True,
                },
            },
        ]
    }
    cleaned = validator._error_and_strip_removed_output_write_workbook_fields(config, issues)  # noqa: SLF001
    assert cleaned["outputs"][0]["write"] == {OUTPUT_WRITE_KEYS["include_header"]: True}  # type: ignore[index]
    assert cleaned["outputs"][1]["write"] == {OUTPUT_WRITE_KEYS["include_header"]: True}  # type: ignore[index]
    assert len(issues) >= 2


def test_validator_strips_removed_sources_retry_multiple_sources_reuses_next_sources() -> None:
    issues = []
    cleaned = {"sources": {"s1": {"retry": {"should_retry": "x"}}, "s2": {"retry": {"should_retry": "y"}}}}
    out = ConfigValidator._strip_removed_source_runtime_policy_keys(cleaned, issues)  # noqa: SLF001

    assert "retry" not in out["sources"]["s1"]  # type: ignore[index]
    assert "retry" not in out["sources"]["s2"]  # type: ignore[index]
    assert len(issues) == 2


def test_validator_strips_removed_sources_lookup_chunk_size() -> None:
    issues = []
    cleaned = {"sources": {"customers": {"lookup_chunk_size": 10, "loader": "x"}}}
    out = ConfigValidator._strip_removed_source_runtime_policy_keys(cleaned, issues)  # noqa: SLF001

    assert "lookup_chunk_size" not in out["sources"]["customers"]  # type: ignore[index]
    assert out["sources"]["customers"]["loader"] == "x"  # type: ignore[index]
    assert len(issues) == 1
    assert "LookupChunking" in issues[0].message


def test_validator_strips_removed_output_write_layout_top_level() -> None:
    issues = []
    cleaned = {"name": "demo", "output_write_layout": "column_chunked", "excel_column_residency": "chunked"}
    out = ConfigValidator._strip_removed_demand_runtime_policy_top_level(cleaned, issues)  # noqa: SLF001

    assert "output_write_layout" not in out
    assert "excel_column_residency" not in out
    assert len(issues) == 2
    assert any("OutputWriteLayout" in i.message for i in issues)
