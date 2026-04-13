from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    FileConfig,
    OutputTargetConfig,
    OutputToConfig,
)
from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, WorkflowOptions, WorkflowRun
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
                        "path": "./out/detail.csv",
                    }
                }
            }
        },
        issues,
    )
    assert any("output root directory" in str(issue.message) for issue in issues)
    assert any(str(issue.path) == "resources.files.detail_csv.path" for issue in issues)


def test_workflow_config_parse_rejects_export_xlsx_path_with_xlsx_suffix() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"now expects an output root directory"):
        _ = parse_mod._parse_book_export_xlsx(  # noqa: SLF001
            {"path": "out.xlsx"},
            path="workflow.resources.books.report.export_xlsx",
        )


def test_workflow_config_parse_rejects_legacy_write_lock_and_csv_file_path() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"write_lock was removed"):
        _ = parse_mod._parse_file_config(  # noqa: SLF001
            {"kind": "csv_file", "path": "out", "write_lock": True},
            path="workflow.resources.files.detail_csv",
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"now expects an output root directory"):
        _ = parse_mod._parse_file_config(  # noqa: SLF001
            {"kind": "csv_file", "path": "out.csv"},
            path="workflow.resources.files.detail_csv",
        )


def test_workflow_compile_helpers_cover_output_root_dir_migration_edges(tmp_path: Path) -> None:
    export_xlsx = BookExportXlsxConfig(path="out", allow_formulas=False)
    patched = compile_mod._apply_book_export_xlsx_patch(  # noqa: SLF001
        export_xlsx,
        {"allow_formulas": True},
        path="workflow.resources.books.mem",
    )
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
        options=WorkflowOptions(),
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
