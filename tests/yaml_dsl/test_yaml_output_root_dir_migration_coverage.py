from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl._internal import resource_override as resource_override_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    FileConfig,
    OutputTargetConfig,
    OutputToConfig,
)
from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, WorkflowRun
from scalim.dsl.yaml_dsl.workflow_config import _parse as parse_mod
from scalim.dsl.yaml_dsl import workflow_compile as compile_mod
from scalim.workflow.errors import ScalimWorkflowConfigError


def test_validator_reports_resources_files_path_suffix_csv_migration_issue() -> None:
    v = ConfigValidator()
    issues = []
    v._validate_resource_output_paths(  # noqa: SLF001
        {
            "resources": {
                "files": {
                    "detail_csv": {
                        "csv_file": {"path": "./out/detail.csv"},
                    }
                }
            }
        },
        issues,
    )
    assert any("output root directory" in str(issue.message) for issue in issues)
    assert any(str(issue.path) == "resources.files.detail_csv.csv_file.path" for issue in issues)


def test_validator_strips_removed_resources_write_lock_fields_under_new_paths() -> None:
    v = ConfigValidator()
    issues = []
    config = {
        "resources": {
            "files": {
                "csv_only": {
                    "csv_file": {"path": "./out", "write_lock": True},
                },
            },
            "books": {
                "legacy_export": {
                    "export_xlsx": {"path": "./out", "write_lock": True},
                },
                "file_branch": {
                    "xlsx_file": {"path": "./out", "write_lock": True},
                },
                "mem_branch": {
                    "xlsx_memory": {"write_lock": True},
                },
                "mem_export": {
                    "xlsx_memory": {"export_xlsx": {"path": "./out", "write_lock": True}},
                },
            },
        }
    }

    cleaned = v._error_and_strip_removed_resources_write_lock_fields(config, issues)  # noqa: SLF001
    paths = {str(item.path) for item in issues}
    assert "resources.files.csv_only.csv_file.write_lock" in paths
    assert "resources.books.legacy_export.export_xlsx.write_lock" in paths
    assert "resources.books.file_branch.xlsx_file.write_lock" in paths
    assert "resources.books.mem_branch.xlsx_memory.write_lock" in paths
    assert "resources.books.mem_export.xlsx_memory.export_xlsx.write_lock" in paths

    assert "write_lock" not in cleaned["resources"]["files"]["csv_only"]["csv_file"]
    assert "write_lock" not in cleaned["resources"]["books"]["legacy_export"]["export_xlsx"]
    assert "write_lock" not in cleaned["resources"]["books"]["file_branch"]["xlsx_file"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_branch"]["xlsx_memory"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_export"]["xlsx_memory"]["export_xlsx"]


def test_validator_strips_removed_resources_write_lock_fields_when_next_cfg_already_exists_and_export_has_no_lock() -> None:
    v = ConfigValidator()
    issues = []
    config = {
        "resources": {
            "files": {
                "csv_both": {
                    "write_lock": True,
                    "csv_file": {"path": "./out", "write_lock": True},
                },
            },
            "books": {
                "file_and_root": {
                    "write_lock": True,
                    "xlsx_file": {"path": "./out", "write_lock": True},
                },
                "mem_and_root": {
                    "write_lock": True,
                    "xlsx_memory": {"write_lock": True},
                },
                "mem_export_no_lock": {
                    "xlsx_memory": {"export_xlsx": {"path": "./out"}},
                },
                "mem_export_with_mem_lock": {
                    "xlsx_memory": {"write_lock": True, "export_xlsx": {"path": "./out", "write_lock": True}},
                },
            },
        }
    }

    cleaned = v._error_and_strip_removed_resources_write_lock_fields(config, issues)  # noqa: SLF001

    assert "write_lock" not in cleaned["resources"]["files"]["csv_both"]
    assert "write_lock" not in cleaned["resources"]["files"]["csv_both"]["csv_file"]
    assert "write_lock" not in cleaned["resources"]["books"]["file_and_root"]
    assert "write_lock" not in cleaned["resources"]["books"]["file_and_root"]["xlsx_file"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_and_root"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_and_root"]["xlsx_memory"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_export_with_mem_lock"]["xlsx_memory"]
    assert "write_lock" not in cleaned["resources"]["books"]["mem_export_with_mem_lock"]["xlsx_memory"]["export_xlsx"]


def test_validator_reports_resources_files_and_books_kind_and_shape_migrations() -> None:
    v = ConfigValidator()
    issues = []
    v._validate_resource_output_paths(  # noqa: SLF001
        {
            "resources": {
                "files": {
                    "legacy_csv": {"kind": "csv_file", "csv_file": {"path": "./out"}},
                    "legacy_other": {"kind": "nope", "csv_file": {"path": "./out"}},
                    "missing_csv_file": {},
                    "csv_file_not_object": {"csv_file": []},
                },
                "books": {
                    "kind_xlsx_file": {"kind": "xlsx_file", "xlsx": {"path": "./out"}},
                    "kind_xlsx_memory": {"kind": "xlsx_memory", "xlsx": {}},
                    "kind_other": {"kind": "nope", "xlsx": {"path": "./out"}},
                    "file_alias": {"xlsx_file": []},
                    "file_alias_obj": {"xlsx_file": {}},
                    "mem_alias": {"xlsx_memory": []},
                    "mem_export_alias": {"xlsx_memory": {"export_xlsx": []}},
                    "mem_export_path_alias": {"xlsx_memory": {"export_xlsx": {}}},
                },
            }
        },
        issues,
    )
    paths = {str(item.path) for item in issues}
    assert "resources.files.legacy_csv.kind" in paths
    assert "resources.files.legacy_other.kind" in paths
    assert "resources.files.missing_csv_file" in paths
    assert "resources.files.csv_file_not_object.csv_file" in paths

    assert "resources.books.kind_xlsx_file.kind" in paths
    assert "resources.books.kind_xlsx_memory.kind" in paths
    assert "resources.books.kind_other.kind" in paths
    assert "resources.books.file_alias.xlsx_file" in paths
    assert "resources.books.file_alias_obj.xlsx_file" in paths
    assert "resources.books.mem_alias.xlsx_memory" in paths
    assert "resources.books.mem_export_alias.xlsx_memory" in paths
    assert "resources.books.mem_export_path_alias.xlsx_memory" in paths
    assert any("xlsx_file was removed" in str(item.message) for item in issues)
    assert any("xlsx_memory was removed" in str(item.message) for item in issues)
    assert any("xlsx_memory with export_xlsx was removed" in str(item.message) for item in issues)


def test_workflow_config_parse_rejects_export_xlsx_path_with_xlsx_suffix() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"now expects an output root directory"):
        _ = parse_mod._parse_book_export_xlsx(  # noqa: SLF001
            {"path": "out.xlsx"},
            path="workflow.resources.books.report.export_xlsx",
        )


def test_workflow_config_parse_book_export_xlsx_and_memory_error_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"must be a mapping") as exc_info:
        _ = parse_mod._parse_book_export_xlsx("nope", path="p.export_xlsx")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx"

    with pytest.raises(ScalimWorkflowConfigError, match=r"has unknown keys: nope") as exc_info:
        _ = parse_mod._parse_book_export_xlsx({"path": "out", "nope": 1}, path="p.export_xlsx")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx"

    with pytest.raises(ScalimWorkflowConfigError, match=r"path is required") as exc_info:
        _ = parse_mod._parse_book_export_xlsx({"path": "   "}, path="p.export_xlsx")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx.path"

    with pytest.raises(ScalimWorkflowConfigError, match=r"allow_formulas must be a bool") as exc_info:
        _ = parse_mod._parse_book_export_xlsx({"path": "out", "allow_formulas": "nope"}, path="p.export_xlsx")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx.allow_formulas"

    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_memory was removed") as exc_info:
        _ = parse_mod._parse_book_config(  # noqa: SLF001
            {"xlsx_memory": {"write_lock": True}},
            path="p",
        )
    assert exc_info.value.path == "p.xlsx_memory"

    with pytest.raises(ScalimWorkflowConfigError, match=r"xlsx_memory was removed") as exc_info:
        _ = parse_mod._parse_book_config(  # noqa: SLF001
            {"xlsx_memory": {"nope": 1}},
            path="p",
        )
    assert exc_info.value.path == "p.xlsx_memory"


def test_workflow_config_parse_rejects_legacy_write_lock_and_csv_file_path() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"write_lock was removed"):
        _ = parse_mod._parse_file_config(  # noqa: SLF001
            {"kind": "csv_file", "path": "out", "write_lock": True},
            path="workflow.resources.files.detail_csv",
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"now expects an output root directory"):
        _ = parse_mod._parse_file_config(  # noqa: SLF001
            {"csv_file": {"path": "out.csv"}},
            path="workflow.resources.files.detail_csv",
        )


def test_workflow_compile_helpers_cover_output_root_dir_migration_edges(tmp_path: Path) -> None:
    export_xlsx = BookExportXlsxConfig(path="out", allow_formulas=False)
    patched = resource_override_mod._apply_optional_book_export_xlsx_patch(  # noqa: SLF001
        export_xlsx,
        {"allow_formulas": True},
        path="workflow.resources.books.mem",
    )
    assert patched is not None
    assert patched.path == "out"
    assert patched.allow_formulas is True

    book = BookConfig(
        kind="xlsx_memory",
        budget=BookBudgetConfig(max_sheets=1, max_total_cells=2),
        export_xlsx=BookExportXlsxConfig(path=str(tmp_path / "out.xlsx"), allow_formulas=True),
    )
    with pytest.raises(ValueError, match=r"export_xlsx\.path now expects an output root directory"):
        _ = compile_mod._book_export_path_and_options(  # noqa: SLF001
            book,
            book_id="mem",
            base_dir=str(tmp_path),
            init_vars=None,
            path_prefix="resources.books.mem",
        )

    file_cfg = FileConfig(kind="csv_file", path=str(tmp_path / "out.csv"), encoding="utf-8")
    with pytest.raises(ValueError, match=r"path now expects an output root directory"):
        _ = compile_mod._file_export_path_and_options(  # noqa: SLF001
            file_cfg,
            file_id="detail_csv",
            base_dir=str(tmp_path),
            init_vars=None,
            path_prefix="resources.files.detail_csv",
        )


def test_append_write_nodes_from_runs_serializes_multiple_writes_to_same_file_id() -> None:
    wf = WorkflowConfig(
        runs=(WorkflowRun(id="r1", demand="demand.yaml"),),
    )
    outputs = (
        OutputTargetConfig(name="o1", to=OutputToConfig(file="detail_csv"), fields=("id",)),
        OutputTargetConfig(name="o2", to=OutputToConfig(file="detail_csv"), fields=("id",)),
    )
    cfg = DemandConfig(
        name="d",
        outputs=outputs,
    )

    nodes = []
    edges = []
    file_cfg = FileConfig(kind="csv_file", path="./out", encoding="utf-8")

    _ = compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
        wf,
        demand_cfg_by_run_id={"r1": cfg},
        nodes=nodes,
        edges=edges,
        effective_books={},
        effective_files={"detail_csv": file_cfg},
        overrides_outputs=None,
        default_book_id=None,
    )

    assert len(nodes) == 2
    assert nodes[1].deps is not None
    assert len(nodes[1].deps) == 2
    assert nodes[0].node_id in nodes[1].deps
