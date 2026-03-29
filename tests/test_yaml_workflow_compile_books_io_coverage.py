from pathlib import Path

import pytest

from scalim.dsl.by_yaml import workflow_compile as workflow_compile_mod
from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, WorkflowConfig, WorkflowOptions, WorkflowRun
from scalim.dsl.by_yaml.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    OutputExtraSheetConfig,
    OutputContainerConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    OutputsDefaultsConfig,
    OutputsDefaultsToConfig,
    ResourcesConfig,
)
from scalim.spec.ir._workflow import AppendSheetNodeIr, WorkflowAnyNodeIr, WorkflowEdgeIr, WorkflowNodeType, WriteSheetNodeIr


def test_workflow_compile_try_resolve_book_export_abs_path_cover_branches(tmp_path: Path) -> None:
    # exception branch -> None
    assert (
        workflow_compile_mod._try_resolve_book_export_abs_path(  # noqa: SLF001
            BookConfig(kind="xlsx_memory"),
            book_id="b",
            base_dir=str(tmp_path),
            init_vars=None,
            path_prefix="resources.books.b",
        )
        is None
    )

    # no export path -> None
    assert (
        workflow_compile_mod._try_resolve_book_export_abs_path(  # noqa: SLF001
            BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1)),
            book_id="b",
            base_dir=str(tmp_path),
            init_vars=None,
            path_prefix="resources.books.b",
        )
        is None
    )

    # success -> abs path
    out = workflow_compile_mod._try_resolve_book_export_abs_path(  # noqa: SLF001
        BookConfig(kind="xlsx_file", path="./a.xlsx"),
        book_id="b",
        base_dir=str(tmp_path),
        init_vars=None,
        path_prefix="resources.books.b",
    )
    assert out is not None
    assert str(out).endswith("a.xlsx")


def test_workflow_compile_validate_excel_sheet_name_errors_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p is required"):
        workflow_compile_mod._validate_excel_sheet_name("", path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"too long"):
        workflow_compile_mod._validate_excel_sheet_name("x" * 32, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"invalid character"):
        workflow_compile_mod._validate_excel_sheet_name("A/B", path="p")  # noqa: SLF001


def test_workflow_compile_effective_book_binding_and_sheet_name_cover_branches() -> None:
    cfg = DemandConfig(outputs_defaults=OutputsDefaultsConfig(to=OutputsDefaultsToConfig(book="base")))
    overrides_outputs_defaults = {"to": {"book": "over"}}

    book, ref = workflow_compile_mod._effective_default_book_id(cfg, overrides_outputs_defaults=overrides_outputs_defaults)  # noqa: SLF001
    assert book == "over"
    assert ref == "overrides.outputs_defaults.to.book"

    out_cfg = OutputTargetConfig(name="detail", to=OutputToConfig(book="report"), fields=("a",))
    book, ref = workflow_compile_mod._effective_book_binding_for_output(  # noqa: SLF001
        cfg,
        out_cfg,
        idx=0,
        outputs_path="outputs",
        overrides_outputs_defaults=None,
    )
    assert book == "report"
    assert ref == "outputs.0.to.book"

    sheet, ref = workflow_compile_mod._effective_sheet_name_for_output(out_cfg, idx=0, outputs_path="outputs")  # noqa: SLF001
    assert sheet == "detail"
    assert ref == "outputs.0.name"


@pytest.mark.parametrize(
    ("override", "match"),
    [
        (OutputWriteConfig(mode="nope"), r"Invalid write\.mode"),
        (OutputWriteConfig(align_by="nope"), r"Invalid write\.align_by"),
        (OutputWriteConfig(header_policy="nope"), r"Invalid write\.header_policy"),
        (OutputWriteConfig(on_mismatch="nope"), r"Invalid write\.on_mismatch"),
        (OutputWriteConfig(on_conflict="nope"), r"Invalid write\.on_conflict"),
    ],
)
def test_workflow_compile_overlay_write_defaults_invalid_enums_cover_branches(override: OutputWriteConfig, match: str) -> None:
    base = workflow_compile_mod._effective_write_defaults(BookConfig(kind="xlsx_file", path="a.xlsx"))  # noqa: SLF001
    with pytest.raises(ValueError, match=match):
        _ = workflow_compile_mod._overlay_write_defaults(base, override)  # noqa: SLF001


def test_workflow_compile_apply_book_patch_error_branches_cover_paths() -> None:
    base = BookConfig(kind="xlsx_file", path="a.xlsx")

    with pytest.raises(ScalimWorkflowConfigError, match=r"p contains unknown keys"):
        _ = workflow_compile_mod._apply_book_patch(base, {"nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.kind must be a non-empty string"):
        _ = workflow_compile_mod._apply_book_patch(base, {"kind": ""}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"allow_formulas must be a bool"):
        _ = workflow_compile_mod._apply_book_patch(base, {"allow_formulas": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"write_lock must be a bool"):
        _ = workflow_compile_mod._apply_book_patch(base, {"write_lock": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget must be a mapping"):
        _ = workflow_compile_mod._apply_book_patch(base, {"budget": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"requires max_sheets and max_total_cells"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"budget": {}}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx must be a mapping"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"export_xlsx": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx\.path is required"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"export_xlsx": {}}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"write_defaults must be a mapping"):
        _ = workflow_compile_mod._apply_book_patch(base, {"write_defaults": "nope"}, path="p")  # noqa: SLF001

    # semantic: xlsx_file requires path
    with pytest.raises(ScalimWorkflowConfigError, match=r"path is required for kind=xlsx_file"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="xlsx_file"), {}, path="p")  # noqa: SLF001

    # semantic: xlsx_memory requires budget
    with pytest.raises(ScalimWorkflowConfigError, match=r"budget is required for kind=xlsx_memory"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {}, path="p")  # noqa: SLF001

    # semantic: unknown kind
    with pytest.raises(ScalimWorkflowConfigError, match=r"kind='nope' is invalid"):
        _ = workflow_compile_mod._apply_book_patch(BookConfig(kind="nope"), {}, path="p")  # noqa: SLF001


def test_workflow_compile_apply_book_patch_success_and_semantic_errors_cover_more_branches() -> None:
    base = BookConfig(kind="xlsx_file", path="a.xlsx")

    patched = workflow_compile_mod._apply_book_patch(  # noqa: SLF001
        base,
        {"path": "b.xlsx", "allow_formulas": True, "write_lock": True, "budget": None},
        path="p",
    )
    assert patched.path == "b.xlsx"
    assert patched.allow_formulas is True
    assert patched.write_lock is True
    assert patched.budget is None

    assert workflow_compile_mod._apply_book_patch(base, {"write_defaults": None}, path="p").write_defaults is None  # noqa: SLF001

    patched = workflow_compile_mod._apply_book_patch(base, {"write_defaults": {"mode": "append"}}, path="p")  # noqa: SLF001
    assert patched.write_defaults is not None
    assert patched.write_defaults.mode == "append"

    base_mem = BookConfig(kind="xlsx_memory")
    created = workflow_compile_mod._apply_book_patch(  # noqa: SLF001
        base_mem,
        {"budget": {"max_sheets": 1, "max_total_cells": 2}, "export_xlsx": {"path": "x.xlsx"}},
        path="p",
    )
    assert created.budget is not None
    assert created.export_xlsx is not None

    updated = workflow_compile_mod._apply_book_patch(  # noqa: SLF001
        created,
        {"budget": {"max_sheets": 3}, "export_xlsx": {"write_lock": True}},
        path="p",
    )
    assert updated.budget is not None
    assert updated.budget.max_sheets == 3
    assert updated.export_xlsx is not None
    assert updated.export_xlsx.write_lock is True

    updated2 = workflow_compile_mod._apply_book_patch(updated, {"budget": {"max_total_cells": 5}}, path="p")  # noqa: SLF001
    assert updated2.budget is not None
    assert updated2.budget.max_total_cells == 5

    cleared = workflow_compile_mod._apply_book_patch(updated, {"export_xlsx": None}, path="p")  # noqa: SLF001
    assert cleared.export_xlsx is None

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget is not allowed for kind=xlsx_file"):
        _ = workflow_compile_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a.xlsx"),
            {"budget": {"max_sheets": 1, "max_total_cells": 1}},
            path="p",
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx is not allowed for kind=xlsx_file"):
        _ = workflow_compile_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a.xlsx"),
            {"export_xlsx": {"path": "x.xlsx"}},
            path="p",
        )

    base_mem = BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1))
    with pytest.raises(ScalimWorkflowConfigError, match=r"path is not allowed for kind=xlsx_memory"):
        _ = workflow_compile_mod._apply_book_patch(base_mem, {"path": "a.xlsx"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"allow_formulas is not allowed for kind=xlsx_memory"):
        _ = workflow_compile_mod._apply_book_patch(base_mem, {"allow_formulas": True}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"write_lock is not allowed for kind=xlsx_memory"):
        _ = workflow_compile_mod._apply_book_patch(base_mem, {"write_lock": True}, path="p")  # noqa: SLF001


def test_workflow_compile_book_export_path_and_options_error_branches_cover_budget_and_unknown_kind() -> None:
    with pytest.raises(ValueError, match=r"requires budget"):
        _ = workflow_compile_mod._book_export_path_and_options(  # noqa: SLF001
            BookConfig(kind="xlsx_memory"),
            book_id="b",
            base_dir=".",
            init_vars=None,
            path_prefix="resources.books.b",
        )

    with pytest.raises(ValueError, match=r"Unknown book kind"):
        _ = workflow_compile_mod._book_export_path_and_options(  # noqa: SLF001
            BookConfig(kind="nope"),
            book_id="b",
            base_dir=".",
            init_vars=None,
            path_prefix="resources.books.b",
        )


def test_workflow_compile_resources_demand_conflicts_and_overrides_cover_branches(tmp_path: Path) -> None:
    workflow_base_dir = tmp_path / "wf"

    run_a = WorkflowRun(id="a", demand="a.yaml")
    run_b = WorkflowRun(id="b", demand="b.yaml")
    wf_obj = WorkflowConfig(runs=(run_a, run_b), options=WorkflowOptions(), resources=ResourcesConfig())

    # missing cfg branch in demand collection loop
    _resources, _effective, _base_dir = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": DemandConfig()},
        demand_yaml_paths_by_run_id={},
        init_vars=None,
        overrides_resources=None,
    )

    # kind mismatch between workflow and demand
    wf_obj = WorkflowConfig(
        runs=(run_a,),
        options=WorkflowOptions(),
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")}),
    )
    demand_cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(1, 1))}))
    with pytest.raises(ScalimWorkflowConfigError, match=r"Book kind mismatch"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": demand_cfg},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
            init_vars=None,
            overrides_resources=None,
        )

    # workflow overrides demand book definition when kind is compatible
    wf_obj = WorkflowConfig(
        runs=(run_a,),
        options=WorkflowOptions(),
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="wf.xlsx")}),
    )
    demand_cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="d.xlsx")}))
    _resources, effective_books, _base_dir = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": demand_cfg},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert effective_books["report"].path == "wf.xlsx"

    # conflicting demand book definitions for same book_id
    wf_obj = WorkflowConfig(runs=(run_a, run_b), options=WorkflowOptions(), resources=ResourcesConfig())
    demand_cfg_a = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")}))
    demand_cfg_b = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="b.xlsx")}))
    with pytest.raises(ScalimWorkflowConfigError, match=r"Conflicting demand book definitions"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": demand_cfg_a, "b": demand_cfg_b},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d1" / "a.yaml"), "b": str(tmp_path / "d1" / "b.yaml")},
            init_vars=None,
            overrides_resources=None,
        )

    # same config, but base_dir mismatch leads to conflicting resolved abs paths
    demand_cfg_a = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}))
    demand_cfg_b = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}))
    with pytest.raises(ScalimWorkflowConfigError, match=r"Conflicting demand book paths"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": demand_cfg_a, "b": demand_cfg_b},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d1" / "a.yaml"), "b": str(tmp_path / "d2" / "b.yaml")},
            init_vars=None,
            overrides_resources=None,
        )

    # demand-only book is accepted and uses demand YAML base_dir semantics
    wf_obj = WorkflowConfig(runs=(run_a,), options=WorkflowOptions(), resources=ResourcesConfig())
    demand_cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}))
    _resources, effective_books, base_dir_by_book_id = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": demand_cfg},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert "report" in effective_books
    assert base_dir_by_book_id["report"] == str(tmp_path / "d")

    # overrides.resources.books keys mismatch (non-str) triggers "continue" branch for unresolved book_id
    resources, effective_books, _base_dir = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        WorkflowConfig(runs=(run_a,), options=WorkflowOptions(), resources=ResourcesConfig()),
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": DemandConfig()},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources={"books": {1: {"kind": "xlsx_file", "path": "a.xlsx"}}},
    )
    assert resources == []
    assert effective_books == {}

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.books\.report must be a mapping"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            WorkflowConfig(runs=(run_a,), options=WorkflowOptions(), resources=ResourcesConfig()),
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": DemandConfig()},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
            init_vars=None,
            overrides_resources={"books": {"report": "nope"}},
        )

    # overrides.resources.books can create a book definition from scratch (IO-only deep-merge)
    _resources, effective_books, base_dir_by_book_id = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        WorkflowConfig(runs=(run_a,), options=WorkflowOptions(), resources=ResourcesConfig()),
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": DemandConfig()},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources={"books": {"report": {"kind": "xlsx_file", "path": "a.xlsx"}}},
    )
    assert effective_books["report"].kind == "xlsx_file"
    assert base_dir_by_book_id["report"] == str(workflow_base_dir)

    # exception wrap branch when export options invalid (xlsx_memory missing budget)
    wf_obj = WorkflowConfig(
        runs=(run_a,), options=WorkflowOptions(), resources=ResourcesConfig(books={"bad": BookConfig(kind="xlsx_memory")})
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"requires budget"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": DemandConfig()},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
            init_vars=None,
            overrides_resources=None,
        )

    # collision branch (two books same path)
    wf_obj = WorkflowConfig(
        runs=(),
        options=WorkflowOptions(),
        resources=ResourcesConfig(
            books={
                "a": BookConfig(kind="xlsx_file", path=str(tmp_path / "same.xlsx")),
                "b": BookConfig(kind="xlsx_file", path=str(tmp_path / "same.xlsx")),
            }
        ),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"path collision"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=None,
        )


def test_workflow_compile_effective_outputs_parser_and_write_node_errors_cover_branches() -> None:
    cfg = DemandConfig()

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.outputs\.0 must be a mapping"):
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(cfg, overrides_outputs=["nope"])  # type: ignore[arg-type]  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"name is required"):
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(cfg, overrides_outputs=[{}])  # noqa: SLF001

    outs = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
        cfg,
        overrides_outputs=[{"name": "detail", "to": {"book": "report", "sheet": "S"}, "write": {"mode": "append"}}],
    )
    assert outs[0].name == "detail"

    # build nodes: cfg missing in mapping -> continue branch
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), options=WorkflowOptions(), resources=ResourcesConfig())
    nodes: list[WorkflowAnyNodeIr] = []
    edges: list[WorkflowEdgeIr] = []
    assert (
        workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={},
            nodes=nodes,
            edges=edges,
            effective_books={},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )
        == {}
    )

    # sheet name validation error path
    cfg = DemandConfig(outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="A/B"), fields=("a",)),))
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), options=WorkflowOptions(), resources=ResourcesConfig())
    with pytest.raises(ScalimWorkflowConfigError, match=r"invalid character"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # unsupported mode error path
    cfg = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="a.xlsx", write_defaults=BookWriteDefaultsConfig(mode="nope"))}
        ),
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="S"), fields=("a",)),),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Unsupported books\.write_defaults\.mode"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": cfg.resources.books["report"]},  # type: ignore[union-attr]
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )


def test_workflow_compile_meta_audit_fallback_and_inject_dependencies_cover_branches() -> None:
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), options=WorkflowOptions(), resources=ResourcesConfig())

    base_cfg = DemandConfig(
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="S"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )

    # fallback to output binding for default book
    nodes: list[WorkflowAnyNodeIr] = []
    edges: list[WorkflowEdgeIr] = []
    out = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
        wf_obj,
        demand_cfg_by_run_id={"a": base_cfg},
        nodes=nodes,
        edges=edges,
        effective_books={"report": BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=10))},
        overrides_outputs=None,
        overrides_outputs_defaults=None,
    )
    assert out["a"]
    assert any(isinstance(n, (WriteSheetNodeIr, AppendSheetNodeIr)) for n in nodes)

    # missing default binding error
    cfg = DemandConfig(
        outputs=(OutputTargetConfig(name="detail", container=OutputContainerConfig(type="csv", path="out.csv"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"meta/audit requires a default books binding"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # default book missing in effective_books
    cfg = DemandConfig(
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="missing", sheet="S"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Missing book resource id"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # invalid extra sheet name error path
    cfg = DemandConfig(
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="S"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="A/B"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"invalid character"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # default book missing in effective_books for extra sheets (outputs are containers)
    cfg = DemandConfig(
        outputs_defaults=OutputsDefaultsConfig(to=OutputsDefaultsToConfig(book="missing")),
        outputs=(OutputTargetConfig(name="detail", container=OutputContainerConfig(type="csv", path="out.csv"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Missing book resource id"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # unsupported mode branch for extra sheets
    cfg = DemandConfig(
        outputs_defaults=OutputsDefaultsConfig(to=OutputsDefaultsToConfig(book="report")),
        outputs=(OutputTargetConfig(name="detail", container=OutputContainerConfig(type="csv", path="out.csv"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Unsupported books\.write_defaults\.mode"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": BookConfig(kind="xlsx_file", path="a.xlsx", write_defaults=BookWriteDefaultsConfig(mode="nope"))},
            overrides_outputs=None,
            overrides_outputs_defaults=None,
        )

    # inject deps: pos None and wrong node type branches
    nodes = [
        WriteSheetNodeIr(node_id="w", node_type=WorkflowNodeType.WRITE_SHEET, decl_order=0, deps=(), resource_type="book", resource_id="r"),
    ]
    workflow_compile_mod._inject_xlsx_memory_write_dependencies(  # noqa: SLF001
        {"a": ["w"]},
        {"a": ["missing_pos", "w"]},
        {"w": 0},
        nodes,  # type: ignore[arg-type]
        edges=[],
    )


def test_workflow_compile_compile_workflow_ir_overrides_mapping_parsing_cover_branches(tmp_path: Path) -> None:
    wf_obj = WorkflowConfig(runs=(), options=WorkflowOptions(), resources=ResourcesConfig())
    ir = workflow_compile_mod.compile_workflow_ir(  # noqa: SLF001
        wf_obj,
        workflow_yaml_path=str(tmp_path / "wf.yaml"),
        path_aliases=None,
        template_vars=None,
        allowed_yaml_roots=None,
        init_vars=None,
        overrides={"resources": {}, "outputs_defaults": {}, "outputs": []},
    )
    assert ir.nodes == ()
