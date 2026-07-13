"""c25: book IR identity is pathful vs pathless (not kind strings)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.book_identity import is_pathful_book, legacy_kind_shim
from scalim.dsl.yaml_dsl._internal.workflow_compile_resources import _book_export_path_and_options
from scalim.dsl.yaml_dsl.schema_dsl.models import BookConfig
from scalim.dsl.yaml_dsl.workflow import load_workflow_config
from scalim.spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowOptionsIr, WorkflowResourceIr
from scalim.vendor.yamlx import yaml
from scalim.workflow.resource_defs import build_workflow_resource_defs


def test_is_pathful_book_ssot_is_path_presence() -> None:
    assert is_pathful_book(BookConfig(kind="xlsx_file", path="./out")) is True
    assert is_pathful_book(BookConfig(kind="xlsx_memory", path=None)) is False
    # kind 字面量不决定身份
    assert is_pathful_book(BookConfig(kind="xlsx_memory", path="./out")) is True
    assert is_pathful_book(BookConfig(kind="xlsx_file", path=None)) is False


def test_compile_emits_pathful_option_and_legacy_kind_shim(tmp_path: Path) -> None:
    root, opts = _book_export_path_and_options(
        BookConfig(kind="xlsx_file", path=str(tmp_path / "out")),
        book_id="report",
        base_dir=str(tmp_path),
        init_vars=None,
        path_prefix="resources.books.report",
    )
    assert root
    assert opts["pathful"] is True
    assert opts["kind"] == legacy_kind_shim(pathful=True)

    root2, opts2 = _book_export_path_and_options(
        BookConfig(kind="xlsx_memory"),
        book_id="scratch",
        base_dir=str(tmp_path),
        init_vars=None,
        path_prefix="resources.books.scratch",
    )
    assert root2 == ""
    assert opts2["pathful"] is False
    assert opts2["kind"] == legacy_kind_shim(pathful=False)


def test_resource_defs_prefer_pathful_flag_over_kind_string(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(
            WorkflowResourceIr(
                resource_id="report",
                resource_type="book",
                path=str(out),
                options={"pathful": True, "allow_formulas": True},
            ),
            WorkflowResourceIr(
                resource_id="scratch",
                resource_type="book",
                path="",
                options={"pathful": False},
            ),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    workbooks, _allow, _csv, sheetbooks = build_workflow_resource_defs(workflow_ir, workflow_exec_id="wf_c25")
    assert "report" in workbooks
    assert "scratch" in sheetbooks


def test_unified_xlsx_yaml_normalizes_to_path_presence_ir(tmp_path: Path) -> None:
    demand = tmp_path / "d.yaml"
    demand.write_text(
        "name: d\nmain_source:\n  source_id: m\n  loader: tests.fixtures.workflow_loaders:load_table_a\n"
        "  fields: {id: {extract: id}}\noutputs: [{name: o, to: {book: report, sheet: S}, fields: [id]}]\n",
        encoding="utf-8",
    )
    wf_path = tmp_path / "wf.yaml"
    wf = {
        "workflow": {
            "resources": {
                "books": {
                    "scratch": {"xlsx": {}},
                    "report": {"xlsx": {"path": str(tmp_path / "out")}},
                }
            },
            "runs": [{"id": "a", "demand": "./d.yaml"}],
        }
    }
    wf_path.write_text(yaml.safe_dump(wf, allow_unicode=True, sort_keys=False), encoding="utf-8")
    cfg = load_workflow_config(str(wf_path))
    assert is_pathful_book(cfg.resources.books["report"]) is True
    assert is_pathful_book(cfg.resources.books["scratch"]) is False
    # deprecated wire shim 仍可派生,但不是身份 SSOT
    assert cfg.resources.books["report"].kind == "xlsx_file"
    assert cfg.resources.books["scratch"].kind == "xlsx_memory"


def test_try_resolve_book_export_abs_path_swallows_resolve_errors(tmp_path: Path) -> None:
    from scalim.dsl.yaml_dsl._internal import workflow_compile_resources as wcr

    assert (
        wcr._try_resolve_book_export_abs_path(  # noqa: SLF001
            BookConfig(kind="xlsx_memory"),
            book_id="scratch",
            base_dir=".",
            init_vars=None,
            path_prefix="resources.books.scratch",
        )
        is None
    )
    # pathful 但 path 误写成 `.xlsx` 文件 → ValueError 被吞掉
    assert (
        wcr._try_resolve_book_export_abs_path(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path=str(tmp_path / "report.xlsx")),
            book_id="report",
            base_dir=str(tmp_path),
            init_vars=None,
            path_prefix="resources.books.report",
        )
        is None
    )


def test_get_book_kind_empty_for_unknown_book_id() -> None:
    from scalim.workflow.resources import WorkflowResourceManager

    mgr = WorkflowResourceManager.__new__(WorkflowResourceManager)
    mgr._workbook_defs = {}  # noqa: SLF001
    mgr._sheetbook_defs = {}  # noqa: SLF001
    assert mgr.get_book_kind("missing") == ""


def test_resource_defs_fallback_legacy_kind_and_reject_unknown(tmp_path: Path) -> None:
    from scalim.workflow.errors import ScalimWorkflowConfigError

    out = tmp_path / "out"
    out.mkdir()
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(
            WorkflowResourceIr(
                resource_id="report",
                resource_type="book",
                path=str(out),
                options={"kind": "xlsx_file", "allow_formulas": True},
            ),
            WorkflowResourceIr(
                resource_id="scratch",
                resource_type="book",
                path="",
                options={"kind": "xlsx_memory"},
            ),
        ),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    workbooks, _allow, _csv, sheetbooks = build_workflow_resource_defs(workflow_ir, workflow_exec_id="wf_c25_legacy")
    assert "report" in workbooks
    assert "scratch" in sheetbooks

    bad_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(WorkflowResourceIr(resource_id="x", resource_type="book", path="", options={"kind": "nope"}),),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    with pytest.raises(ScalimWorkflowConfigError, match="Unknown book identity"):
        _ = build_workflow_resource_defs(bad_ir, workflow_exec_id="wf_c25_bad")
