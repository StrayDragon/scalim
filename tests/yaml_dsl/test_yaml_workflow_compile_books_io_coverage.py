from pathlib import Path

import os
import pytest

from scalim.dsl.yaml_dsl import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    FileResourceOverride,
    OutputExtraSheetOverride,
    OutputDefaultsToOverride,
    OutputsDefaultsOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOverrides,
)
from scalim.dsl.yaml_dsl._internal import resource_override as resource_override_mod
from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError, WorkflowConfig, WorkflowRun
from scalim.dsl.yaml_dsl.init_var_nodes import ScalimInitVarNodeValueError, parse_init_var_mapping_node
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    ResourcesConfig,
)
from scalim.spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowEdgeIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WriteSheetNodeIr,
)


def test_workflow_compile_try_resolve_book_export_abs_path_cover_branches(tmp_path: Path) -> None:
    # exception branch -> None
    assert (
        workflow_compile_mod._try_resolve_book_export_abs_path(  # noqa: SLF001
            BookConfig(kind="nope"),
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
        BookConfig(kind="xlsx_file", path="./a"),
        book_id="b",
        base_dir=str(tmp_path),
        init_vars=None,
        path_prefix="resources.books.b",
    )
    assert out is not None
    assert str(out) == str((tmp_path / "a").resolve(strict=False))


def test_workflow_compile_validate_excel_sheet_name_errors_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p: Excel sheet name must be non-empty.*Hint:"):
        workflow_compile_mod._validate_excel_sheet_name("", path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"too long"):
        workflow_compile_mod._validate_excel_sheet_name("x" * 32, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"invalid characters"):
        workflow_compile_mod._validate_excel_sheet_name("A/B", path="p")  # noqa: SLF001


def test_workflow_compile_effective_book_binding_and_sheet_name_cover_branches() -> None:
    out_cfg = OutputTargetConfig(name="detail", to=OutputToConfig(book="report"), fields=("a",))
    book, ref = workflow_compile_mod._effective_book_binding_for_output(  # noqa: SLF001
        out_cfg,
        idx=0,
        outputs_path="outputs",
    )
    assert book == "report"
    assert ref == "outputs.0.to.book"

    blank_book, blank_ref = workflow_compile_mod._effective_book_binding_for_output(  # noqa: SLF001
        OutputTargetConfig(name="detail", to=OutputToConfig(book="  "), fields=("a",)),
        idx=2,
        outputs_path="outputs",
    )
    assert blank_book is None
    assert blank_ref == "outputs.2.to.book"

    missing_book, missing_ref = workflow_compile_mod._effective_book_binding_for_output(  # noqa: SLF001
        OutputTargetConfig(name="detail", fields=("a",)),
        idx=1,
        outputs_path="outputs",
    )
    assert missing_book is None
    assert missing_ref == "outputs.1.to.book"

    sheet, ref = workflow_compile_mod._effective_sheet_name_for_output(out_cfg, idx=0, outputs_path="outputs")  # noqa: SLF001
    assert sheet == "detail"
    assert ref == "outputs.0.name"


def test_workflow_compile_effective_file_binding_for_output_handles_empty_strings() -> None:
    out_cfg = OutputTargetConfig(name="detail", to=OutputToConfig(file="detail_csv"), fields=("a",))
    file_id, ref = workflow_compile_mod._effective_file_binding_for_output(  # noqa: SLF001
        out_cfg,
        idx=0,
        outputs_path="outputs",
    )
    assert file_id == "detail_csv"
    assert ref == "outputs.0.to.file"

    blank_file_id, blank_ref = workflow_compile_mod._effective_file_binding_for_output(  # noqa: SLF001
        OutputTargetConfig(name="detail", to=OutputToConfig(file="  "), fields=("a",)),
        idx=1,
        outputs_path="outputs",
    )
    assert blank_file_id is None
    assert blank_ref == "outputs.1.to.file"

    missing_file_id, missing_ref = workflow_compile_mod._effective_file_binding_for_output(  # noqa: SLF001
        OutputTargetConfig(name="detail", fields=("a",)),
        idx=2,
        outputs_path="outputs",
    )
    assert missing_file_id is None
    assert missing_ref == "outputs.2.to.file"


def test_workflow_compile_parse_output_extra_sheet_override_branches_cover_errors_and_success() -> None:
    assert resource_override_mod.parse_output_extra_sheet_override(None, path="p") is None  # noqa: SLF001
    assert resource_override_mod.parse_output_extra_sheet_override(False, path="p") is None  # noqa: SLF001

    cfg = resource_override_mod.parse_output_extra_sheet_override(True, path="p")  # noqa: SLF001
    assert cfg == OutputExtraSheetConfig()

    with pytest.raises(ScalimWorkflowConfigError, match=r"p must be a boolean or an OutputExtraSheetOverride"):
        _ = resource_override_mod.parse_output_extra_sheet_override(1, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.parse_output_extra_sheet_override(OutputExtraSheetOverride(path=1), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.path"

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.allow_formulas must be a bool"):
        _ = resource_override_mod.parse_output_extra_sheet_override(
            OutputExtraSheetOverride(allow_formulas="nope"),
            path="p",
        )  # noqa: SLF001

    cfg = resource_override_mod.parse_output_extra_sheet_override(
        OutputExtraSheetOverride(path="./a.xlsx", sheet=" S ", allow_formulas=True),
        path="p",
    )  # noqa: SLF001
    assert cfg is not None
    assert cfg.path == "./a.xlsx"
    assert cfg.sheet == "S"
    assert cfg.allow_formulas is True


class _BlankPathLike(os.PathLike):
    def __init__(self, value: str) -> None:
        self._value = str(value)

    def __fspath__(self) -> str:
        return self._value


def test_resource_override_as_opt_non_empty_str_or_pathlike_cover_branches() -> None:
    assert resource_override_mod._as_opt_non_empty_str_or_pathlike(None, path="p") is None  # noqa: SLF001
    assert resource_override_mod._as_opt_non_empty_str_or_pathlike(_BlankPathLike(" x "), path="p") == "x"  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_non_empty_str_or_pathlike(_BlankPathLike("   "), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_non_empty_str_or_pathlike("   ", path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_non_empty_str_or_pathlike(1, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"


def test_init_var_nodes_parse_mapping_node_missing_key_cover_branches() -> None:
    with pytest.raises(ScalimInitVarNodeValueError) as exc_info:
        _ = parse_init_var_mapping_node({}, path="p")
    assert exc_info.value.path == "p"
    assert "missing '$init_var'" in exc_info.value.reason


@pytest.mark.parametrize(
    ("patch", "match", "expected_path"),
    [
        ({"nope": "x"}, r"contains unknown keys", "p"),
        ({"mode": 1}, r"p\.mode must be a string", "p.mode"),
        ({"mode": "nope"}, r"Invalid write_defaults\.mode", "p.mode"),
        ({"align_by": "nope"}, r"Invalid write_defaults\.align_by", "p.align_by"),
        ({"header_policy": "nope"}, r"Invalid write_defaults\.header_policy", "p.header_policy"),
        ({"on_mismatch": "nope"}, r"Invalid write_defaults\.on_mismatch", "p.on_mismatch"),
        ({"on_conflict": "nope"}, r"Invalid write_defaults\.on_conflict", "p.on_conflict"),
    ],
)
def test_workflow_compile_overlay_book_write_defaults_patch_error_branches_cover_paths(patch: dict, match: str, expected_path: str) -> None:
    base = workflow_compile_mod._effective_write_defaults(BookConfig(kind="xlsx_file", path="a"))  # noqa: SLF001
    with pytest.raises(ScalimWorkflowConfigError, match=match) as exc_info:
        _ = resource_override_mod._overlay_book_write_defaults_patch(base, patch, path="p")  # noqa: SLF001
    assert exc_info.value.path == expected_path


def test_workflow_compile_overlay_book_write_defaults_patch_allows_none_values_as_noop() -> None:
    base = workflow_compile_mod._effective_write_defaults(BookConfig(kind="xlsx_file", path="a"))  # noqa: SLF001
    out = resource_override_mod._overlay_book_write_defaults_patch(base, {"mode": None}, path="p")  # noqa: SLF001
    assert out == base


def test_workflow_compile_apply_overrides_output_extras_rejects_invalid_type_cover_branches() -> None:
    overrides = RunOverrides()
    object.__setattr__(overrides, "output_extras", object())

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.output_extras must be an OutputExtrasOverride"):
        _ = workflow_compile_mod._apply_overrides_output_extras(  # noqa: SLF001
            {"a": DemandConfig()},
            overrides=overrides,
        )


def test_workflow_compile_extra_sheets_unsupported_mode_branch_is_defensive_and_covered() -> None:
    class _FlakyBooks:
        def __init__(self, items: list) -> None:
            self._items = list(items)

        def get(self, _key: str, default=None):  # type: ignore[no-untyped-def]
            if self._items:
                return self._items.pop(0)
            return default

    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())
    cfg = DemandConfig(
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="S"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )

    nodes: list[WorkflowAnyNodeIr] = []
    edges: list[WorkflowEdgeIr] = []
    with pytest.raises(ScalimWorkflowConfigError, match=r"Unsupported books\.write_defaults\.mode"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=nodes,
            edges=edges,
            effective_books=_FlakyBooks(
                [
                    BookConfig(kind="xlsx_file", path="a", write_defaults=BookWriteDefaultsConfig(mode="append")),
                    BookConfig(kind="xlsx_file", path="a", write_defaults=BookWriteDefaultsConfig(mode="nope")),
                ]
            ),
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )
    assert nodes


def test_workflow_compile_apply_book_patch_error_branches_cover_paths() -> None:
    base = BookConfig(kind="xlsx_file", path="a")

    with pytest.raises(ScalimWorkflowConfigError, match=r"p contains unknown keys") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"nope": 1}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.kind must be a non-empty string") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"kind": ""}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.kind must be a non-empty string") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"kind": None}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError, match=r"allow_formulas must be a bool") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"allow_formulas": "nope"}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.allow_formulas"

    with pytest.raises(ScalimWorkflowConfigError, match=r"p contains unknown keys: write_lock") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"write_lock": "nope"}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget must be a mapping") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"budget": "nope"}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget"

    with pytest.raises(ScalimWorkflowConfigError, match=r"requires max_sheets and max_total_cells") as exc_info:
        _ = resource_override_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"budget": {}}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget"

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx must be a mapping") as exc_info:
        _ = resource_override_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"export_xlsx": "nope"}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx"

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx\.path is required") as exc_info:
        _ = resource_override_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {"export_xlsx": {}}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx.path"

    with pytest.raises(ScalimWorkflowConfigError, match=r"write_defaults must be a mapping") as exc_info:
        _ = resource_override_mod._apply_book_patch(base, {"write_defaults": "nope"}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.write_defaults"

    # semantic: xlsx_file requires path
    with pytest.raises(ScalimWorkflowConfigError, match=r"path is required for kind=xlsx_file"):
        _ = resource_override_mod._apply_book_patch(BookConfig(kind="xlsx_file"), {}, path="p")  # noqa: SLF001

    # semantic: xlsx_memory budget is optional (defaults to unlimited)
    patched_unlimited = resource_override_mod._apply_book_patch(BookConfig(kind="xlsx_memory"), {}, path="p")  # noqa: SLF001
    assert patched_unlimited.budget is None

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget\.max_sheets must be >= 1") as exc_info:
        _ = resource_override_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_memory"),
            {"budget": {"max_sheets": 0, "max_total_cells": 1}},
            path="p",
        )
    assert exc_info.value.path == "p.budget.max_sheets"

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget\.max_total_cells must be >= 1") as exc_info2:
        _ = resource_override_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_memory"),
            {"budget": {"max_sheets": 1, "max_total_cells": 0}},
            path="p",
        )
    assert exc_info2.value.path == "p.budget.max_total_cells"

    # semantic: unknown kind
    with pytest.raises(ScalimWorkflowConfigError, match=r"kind='nope' is invalid"):
        _ = resource_override_mod._apply_book_patch(BookConfig(kind="nope"), {}, path="p")  # noqa: SLF001


def test_workflow_compile_apply_book_patch_success_and_semantic_errors_cover_more_branches() -> None:
    base = BookConfig(kind="xlsx_file", path="a")

    patched = resource_override_mod._apply_book_patch(  # noqa: SLF001
        base,
        {"path": "b", "allow_formulas": True, "budget": None},
        path="p",
    )
    assert patched.path == "b"
    assert patched.allow_formulas is True
    assert patched.budget is None

    assert resource_override_mod._apply_book_patch(base, {"write_defaults": None}, path="p").write_defaults is None  # noqa: SLF001

    patched = resource_override_mod._apply_book_patch(base, {"write_defaults": {"mode": "append"}}, path="p")  # noqa: SLF001
    assert patched.write_defaults is not None
    assert patched.write_defaults.mode == "append"

    base_mem = BookConfig(kind="xlsx_memory")
    created = resource_override_mod._apply_book_patch(  # noqa: SLF001
        base_mem,
        {"budget": {"max_sheets": 1, "max_total_cells": 2}, "export_xlsx": {"path": "x"}},
        path="p",
    )
    assert created.budget is not None
    assert created.export_xlsx is not None

    updated = resource_override_mod._apply_book_patch(created, {"budget": {"max_sheets": 3}}, path="p")  # noqa: SLF001
    assert updated.budget is not None
    assert updated.budget.max_sheets == 3
    assert updated.export_xlsx is not None

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx\.write_lock was removed") as exc_info:
        _ = resource_override_mod._apply_book_patch(updated, {"export_xlsx": {"write_lock": True}}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx.write_lock"

    updated2 = resource_override_mod._apply_book_patch(updated, {"budget": {"max_total_cells": 5}}, path="p")  # noqa: SLF001
    assert updated2.budget is not None
    assert updated2.budget.max_total_cells == 5

    cleared = resource_override_mod._apply_book_patch(updated, {"export_xlsx": None}, path="p")  # noqa: SLF001
    assert cleared.export_xlsx is None

    with pytest.raises(ScalimWorkflowConfigError, match=r"budget is not allowed for kind=xlsx_file"):
        _ = resource_override_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a"),
            {"budget": {"max_sheets": 1, "max_total_cells": 1}},
            path="p",
        )

    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx is not allowed for kind=xlsx_file"):
        _ = resource_override_mod._apply_book_patch(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a"),
            {"export_xlsx": {"path": "x"}},
            path="p",
        )

    base_mem = BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1))
    with pytest.raises(ScalimWorkflowConfigError, match=r"path is not allowed for kind=xlsx_memory"):
        _ = resource_override_mod._apply_book_patch(base_mem, {"path": "a"}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"allow_formulas is not allowed for kind=xlsx_memory"):
        _ = resource_override_mod._apply_book_patch(base_mem, {"allow_formulas": True}, path="p")  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"p contains unknown keys: write_lock"):
        _ = resource_override_mod._apply_book_patch(base_mem, {"write_lock": True}, path="p")  # noqa: SLF001


def test_workflow_compile_book_export_path_and_options_error_branches_cover_budget_and_unknown_kind() -> None:
    root, opts = workflow_compile_mod._book_export_path_and_options(  # noqa: SLF001
        BookConfig(kind="xlsx_memory"),
        book_id="b",
        base_dir=".",
        init_vars=None,
        path_prefix="resources.books.b",
    )
    assert root == ""
    assert opts == {"kind": "xlsx_memory"}

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
    wf_obj = WorkflowConfig(runs=(run_a, run_b), resources=ResourcesConfig())

    # missing cfg branch in demand collection loop
    _resources, _effective, _effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
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
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="a")}),
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
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="wf_out")}),
    )
    demand_cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="d_out")}))
    _resources, effective_books, _effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": demand_cfg},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert effective_books["report"].path == "wf_out"

    # conflicting demand book definitions for same book_id
    wf_obj = WorkflowConfig(runs=(run_a, run_b), resources=ResourcesConfig())
    demand_cfg_a = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="a_out")}))
    demand_cfg_b = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="b_out")}))
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
    demand_cfg_a = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out")}))
    demand_cfg_b = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out")}))
    with pytest.raises(ScalimWorkflowConfigError, match=r"Conflicting demand book paths"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": demand_cfg_a, "b": demand_cfg_b},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d1" / "a.yaml"), "b": str(tmp_path / "d2" / "b.yaml")},
            init_vars=None,
            overrides_resources=None,
        )

    # same config, same base_dir: duplicate ids are accepted, and loops continue when later items exist
    demand_cfg_a = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="./out")},
            files={"detail_csv": FileConfig(kind="csv_file", path="./out", encoding="utf-8")},
        )
    )
    demand_cfg_b = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(kind="xlsx_file", path="./out"),
                "extra": BookConfig(kind="xlsx_file", path="./extra"),
            },
            files={
                "detail_csv": FileConfig(kind="csv_file", path="./out", encoding="utf-8"),
                "extra_csv": FileConfig(kind="csv_file", path="./extra", encoding="utf-8"),
            },
        )
    )
    _resources, effective_books, effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": demand_cfg_a, "b": demand_cfg_b},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml"), "b": str(tmp_path / "d" / "b.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert "report" in effective_books and "extra" in effective_books
    assert "detail_csv" in effective_files and "extra_csv" in effective_files

    # demand-only book is accepted and uses demand YAML base_dir semantics
    wf_obj = WorkflowConfig(runs=(run_a,), resources=ResourcesConfig())
    demand_cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out")}))
    resources, effective_books, effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": demand_cfg},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert "report" in effective_books
    assert effective_files == {}
    assert [res.path for res in resources if res.resource_id == "report"] == [str((tmp_path / "d" / "out").resolve())]

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            WorkflowConfig(runs=(run_a,), resources=ResourcesConfig()),
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": DemandConfig()},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
            init_vars=None,
            overrides_resources=ResourcesOverride(books={1: BookResourceOverride(kind="xlsx_file", path="a")}),  # type: ignore[dict-item]
        )
    assert exc_info.value.path == "overrides.resources.books"

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.books\.report must be a BookResourceOverride"):
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            WorkflowConfig(runs=(run_a,), resources=ResourcesConfig()),
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={"a": DemandConfig()},
            demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
            init_vars=None,
            overrides_resources=ResourcesOverride(books={"report": "nope"}),  # type: ignore[dict-item]
        )

    # overrides.resources.books can create a book definition from scratch (IO-only deep-merge)
    resources, effective_books, effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        WorkflowConfig(runs=(run_a,), resources=ResourcesConfig()),
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": DemandConfig()},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=ResourcesOverride(books={"report": BookResourceOverride(kind="xlsx_file", path="a")}),
    )
    assert effective_books["report"].kind == "xlsx_file"
    assert effective_files == {}
    assert [res.path for res in resources if res.resource_id == "report"] == [str((workflow_base_dir / "a").resolve())]

    # xlsx_memory budget can be omitted (treated as unlimited)
    wf_obj = WorkflowConfig(
        runs=(run_a,),
        resources=ResourcesConfig(books={"bad": BookConfig(kind="xlsx_memory")}),
    )
    resources, effective_books, effective_files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id={"a": DemandConfig()},
        demand_yaml_paths_by_run_id={"a": str(tmp_path / "d" / "a.yaml")},
        init_vars=None,
        overrides_resources=None,
    )
    assert effective_books["bad"].kind == "xlsx_memory"
    assert effective_books["bad"].budget is None
    assert effective_files == {}
    assert [res.resource_id for res in resources] == ["bad"]

    # legacy file-path semantics are rejected (xlsx_file.path expects output root dir, not *.xlsx)
    wf_obj = WorkflowConfig(
        runs=(),
        resources=ResourcesConfig(
            books={
                "a": BookConfig(kind="xlsx_file", path=str(tmp_path / "same.xlsx")),
            }
        ),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"expects an output root directory") as exc_info:
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=workflow_base_dir,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=None,
        )
    assert exc_info.value.path == "workflow.resources.books.a"


def test_workflow_compile_resources_override_to_patch_covers_all_optional_fields(tmp_path: Path) -> None:
    wf_obj = WorkflowConfig(runs=(), resources=ResourcesConfig())
    overrides_resources = ResourcesOverride(
        books={
            "report": BookResourceOverride(
                kind="xlsx_file",
                path="./report_root",
                allow_formulas=True,
                write_defaults=BookWriteDefaultsOverride(
                    mode="append",
                    align_by="header",
                    header_policy="always",
                    on_mismatch="error",
                    on_conflict="error",
                ),
            ),
            "mem": BookResourceOverride(
                kind="xlsx_memory",
                budget=BookBudgetOverride(max_sheets=1, max_total_cells=2),
                export_xlsx=BookExportXlsxOverride(path="./mem_root", allow_formulas=True),
                write_defaults=BookWriteDefaultsOverride(mode="append"),
            ),
        },
        files={
            "detail_csv": FileResourceOverride(kind="csv_file", path="./out_root", encoding="latin1"),
        },
    )

    resources, books, files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=tmp_path,
        demand_cfg_by_run_id={},
        demand_yaml_paths_by_run_id={},
        init_vars=None,
        overrides_resources=overrides_resources,
    )
    assert resources
    assert books["report"].allow_formulas is True
    assert books["report"].write_defaults is not None
    assert books["mem"].budget is not None
    assert books["mem"].export_xlsx is not None
    assert files["detail_csv"].encoding == "latin1"


def test_workflow_compile_resources_override_to_patch_supports_partial_overrides_and_ignores_none_fields() -> None:
    updated = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_file", path="a"),
        BookResourceOverride(path="./out"),
        path="p",
    )
    assert updated.path == "./out"

    base_budget = BookBudgetConfig(max_sheets=1, max_total_cells=1)
    updated2 = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_memory", budget=base_budget),
        BookResourceOverride(kind="xlsx_memory", budget=BookBudgetOverride(max_sheets=None, max_total_cells=2)),
        path="p",
    )
    assert updated2.budget is not None
    assert updated2.budget.max_sheets == 1
    assert updated2.budget.max_total_cells == 2

    updated3 = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_memory", budget=base_budget),
        BookResourceOverride(kind="xlsx_memory", budget=BookBudgetOverride(max_sheets=2, max_total_cells=None)),
        path="p",
    )
    assert updated3.budget is not None
    assert updated3.budget.max_sheets == 2
    assert updated3.budget.max_total_cells == 1

    updated4 = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_memory", export_xlsx=BookExportXlsxConfig(path="./x", allow_formulas=False)),
        BookResourceOverride(kind="xlsx_memory", export_xlsx=BookExportXlsxOverride(path=None, allow_formulas=True)),
        path="p",
    )
    assert updated4.export_xlsx is not None
    assert updated4.export_xlsx.path == "./x"
    assert updated4.export_xlsx.allow_formulas is True

    updated5 = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_memory", export_xlsx=BookExportXlsxConfig(path="./x0", allow_formulas=True)),
        BookResourceOverride(kind="xlsx_memory", export_xlsx=BookExportXlsxOverride(path="./x", allow_formulas=None)),
        path="p",
    )
    assert updated5.export_xlsx is not None
    assert updated5.export_xlsx.path == "./x"
    assert updated5.export_xlsx.allow_formulas is True

    updated6 = resource_override_mod.apply_book_resource_override(
        BookConfig(kind="xlsx_file", path="a"),
        BookResourceOverride(kind="xlsx_file", write_defaults=BookWriteDefaultsOverride(mode=None, align_by="header")),
        path="p",
    )
    assert updated6.write_defaults is not None
    assert updated6.write_defaults.align_by == "header"

    file = resource_override_mod.apply_file_resource_override(
        FileConfig(kind="csv_file", path="./out", encoding="utf-8"),
        FileResourceOverride(path=None, encoding="latin1"),
        path="p",
    )
    assert file.encoding == "latin1"


def test_workflow_compile_resources_override_updates_existing_workflow_book(tmp_path: Path) -> None:
    wf_obj = WorkflowConfig(
        runs=(),
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./wf")}),
    )
    resources, books, _files = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
        wf_obj,
        workflow_base_dir=tmp_path,
        demand_cfg_by_run_id={},
        demand_yaml_paths_by_run_id={},
        init_vars=None,
        overrides_resources=ResourcesOverride(books={"report": BookResourceOverride(path="./override")}),
    )
    assert resources
    assert books["report"].path == "./override"


def test_workflow_compile_outputs_defaults_book_id_and_default_binding_cover_branches() -> None:
    assert workflow_compile_mod._parse_overrides_outputs_defaults_book_id(None) is None  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.outputs_defaults\.to\.book is required"):
        _ = workflow_compile_mod._parse_overrides_outputs_defaults_book_id(  # noqa: SLF001
            OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="  "))
        )

    assert (
        workflow_compile_mod._parse_overrides_outputs_defaults_book_id(  # noqa: SLF001
            OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="report"))
        )
        == "report"
    )

    outputs = (
        OutputTargetConfig(name="detail", to=None, fields=("a",)),
        OutputTargetConfig(name="sheet_only", to=OutputToConfig(sheet="S"), fields=("a",)),
        OutputTargetConfig(name="bound", to=OutputToConfig(book="report"), fields=("a",)),
    )
    assert workflow_compile_mod._apply_default_book_binding_to_outputs((), default_book_id="report") == ()  # noqa: SLF001
    assert workflow_compile_mod._apply_default_book_binding_to_outputs(outputs, default_book_id="") is outputs  # noqa: SLF001

    bound = workflow_compile_mod._apply_default_book_binding_to_outputs(outputs, default_book_id="report")  # noqa: SLF001
    assert bound[0].to is not None
    assert bound[0].to.book == "report"
    assert bound[1].to is not None
    assert bound[1].to.book == "report"
    assert bound[1].to.sheet == "S"
    assert bound[2].to is not None
    assert bound[2].to.book == "report"

    effective = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
        DemandConfig(outputs=(OutputTargetConfig(name="detail", to=None, fields=("a",)),)),
        overrides_outputs=None,
        default_book_id="report",
    )
    assert effective[0].to is not None
    assert effective[0].to.book == "report"


def test_workflow_compile_effective_outputs_rejects_bad_typed_overrides_shapes_cover_branches() -> None:
    cfg = DemandConfig()

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            cfg,
            overrides_outputs=[OutputOverride(name="detail", fields=("a",), to=object())],  # type: ignore[arg-type]
            default_book_id=None,
        )
    assert exc_info.value.path == "overrides.outputs.0.to"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            cfg,
            overrides_outputs=[OutputOverride(name="detail", fields=("a",), to=OutputToOverride(sheet="S"))],
            default_book_id=None,
        )
    assert exc_info.value.path == "overrides.outputs.0.to"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            cfg,
            overrides_outputs=[
                OutputOverride(
                    name="detail",
                    fields=("a",),
                    to=OutputToOverride(book="report", sheet="S"),
                    write=object(),  # type: ignore[arg-type]
                )
            ],
            default_book_id=None,
        )
    assert exc_info.value.path == "overrides.outputs.0.write"


def test_workflow_compile_effective_outputs_parser_and_write_node_errors_cover_branches() -> None:
    cfg = DemandConfig()

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.outputs\.0 must be an OutputOverride"):
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # type: ignore[arg-type]  # noqa: SLF001
            cfg,
            overrides_outputs=["nope"],
            default_book_id=None,
        )

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            cfg,
            overrides_outputs=[OutputOverride(name="", fields=(), to=OutputToOverride(book="report", sheet="S"))],
            default_book_id=None,
        )
    assert exc_info.value.path == "overrides.outputs.0.name"

    outs = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
        cfg,
        overrides_outputs=[
            OutputOverride(
                name="detail",
                fields=("a",),
                to=OutputToOverride(book="report", sheet="S"),
                write=OutputWriteOverride(include_header=True),
            )
        ],
        default_book_id=None,
    )
    assert outs[0].name == "detail"

    outs2 = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
        cfg,
        overrides_outputs=[
            OutputOverride(
                name="detail2",
                fields=("a",),
                to=OutputToOverride(book="report", sheet="S"),
            )
        ],
        default_book_id=None,
    )
    assert outs2[0].write is None

    # build nodes: cfg missing in mapping -> continue branch
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())
    nodes: list[WorkflowAnyNodeIr] = []
    edges: list[WorkflowEdgeIr] = []
    assert (
        workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={},
            nodes=nodes,
            edges=edges,
            effective_books={},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )
        == {}
    )

    # missing explicit to.book binding
    cfg = DemandConfig(outputs=(OutputTargetConfig(name="detail", fields=("a",)),))
    with pytest.raises(ScalimWorkflowConfigError, match=r"Missing outputs to\.book binding"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )

    # sheet name validation error path
    cfg = DemandConfig(outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(book="report", sheet="A/B"), fields=("a",)),))
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())
    with pytest.raises(ScalimWorkflowConfigError, match=r"invalid character"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": BookConfig(kind="xlsx_file", path="a")},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )

    # unsupported mode error path
    cfg = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="a", write_defaults=BookWriteDefaultsConfig(mode="nope"))}
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
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )


def test_workflow_compile_rejects_xlsx_memory_align_by_header() -> None:
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())
    cfg = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("a",),
            ),
        ),
    )

    with pytest.raises(ScalimWorkflowConfigError, match=r"canonical field keys"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={
                "report": BookConfig(
                    kind="xlsx_memory",
                    budget=BookBudgetConfig(max_sheets=1, max_total_cells=10),
                    write_defaults=BookWriteDefaultsConfig(mode="append", align_by="header"),
                )
            },
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )


def test_workflow_compile_accepts_xlsx_memory_align_by_field_id() -> None:
    workflow_compile_mod._validate_xlsx_memory_align_by(  # noqa: SLF001
        book=BookConfig(
            kind="xlsx_memory",
            budget=BookBudgetConfig(max_sheets=1, max_total_cells=10),
            write_defaults=BookWriteDefaultsConfig(mode="append", align_by="field_id"),
        ),
        book_id="report",
    )


def test_workflow_compile_default_book_write_mode_is_sheet() -> None:
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())
    cfg = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("a",),
            ),
        ),
    )

    nodes: list[WorkflowAnyNodeIr] = []
    _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
        wf_obj,
        demand_cfg_by_run_id={"a": cfg},
        nodes=nodes,
        edges=[],
        effective_books={"report": BookConfig(kind="xlsx_file", path="out")},
        effective_files={},
        overrides_outputs=None,
        default_book_id=None,
    )
    assert any(isinstance(n, WriteSheetNodeIr) for n in nodes)
    assert not any(isinstance(n, AppendSheetNodeIr) for n in nodes)


def test_workflow_compile_meta_audit_fallback_and_inject_dependencies_cover_branches() -> None:
    wf_obj = WorkflowConfig(runs=(WorkflowRun(id="a", demand="a.yaml"),), resources=ResourcesConfig())

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
        effective_files={},
        overrides_outputs=None,
        default_book_id=None,
    )
    assert out["a"]
    assert any(isinstance(n, (WriteSheetNodeIr, AppendSheetNodeIr)) for n in nodes)

    # missing default binding error
    cfg = DemandConfig(
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="out")}),
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(file="detail_csv"), fields=("a",)),),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"meta/audit requires at least one Excel output with outputs\[\*\]\.to\.book"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={},
            effective_files={"detail_csv": FileConfig(kind="csv_file", path="out")},
            overrides_outputs=None,
            default_book_id=None,
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
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
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
            effective_books={"report": BookConfig(kind="xlsx_file", path="a")},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
        )

    # unsupported mode branch for extra sheets
    cfg = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("a",),
            ),
        ),
        meta=OutputExtraSheetConfig(sheet="__meta__"),
    )
    with pytest.raises(ScalimWorkflowConfigError, match=r"Unsupported books\.write_defaults\.mode"):
        _ = workflow_compile_mod._append_write_nodes_from_runs(  # noqa: SLF001
            wf_obj,
            demand_cfg_by_run_id={"a": cfg},
            nodes=[],
            edges=[],
            effective_books={"report": BookConfig(kind="xlsx_file", path="a", write_defaults=BookWriteDefaultsConfig(mode="nope"))},
            effective_files={},
            overrides_outputs=None,
            default_book_id=None,
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

    # inject deps: already present -> noop branches
    nodes2 = [
        WorkflowNodeIr(
            node_id="consumer",
            node_type=WorkflowNodeType.DEMAND,
            decl_order=0,
            deps=("w",),
        )
    ]
    edges2: list[WorkflowEdgeIr] = []
    workflow_compile_mod._inject_xlsx_memory_write_dependencies(  # noqa: SLF001
        {"a": ["w"]},
        {"a": ["consumer"]},
        {"consumer": 0},
        nodes2,  # type: ignore[arg-type]
        edges=edges2,
    )
    assert nodes2[0].deps == ("w",)
    assert edges2 == []


def test_workflow_compile_compile_workflow_ir_overrides_mapping_parsing_cover_branches(tmp_path: Path) -> None:
    wf_obj = WorkflowConfig(runs=(), resources=ResourcesConfig())
    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides must be a RunOverrides"):
        _ = workflow_compile_mod.compile_workflow_ir(  # noqa: SLF001
            wf_obj,
            workflow_yaml_path=str(tmp_path / "wf.yaml"),
            path_aliases=None,
            template_vars=None,
            allowed_yaml_roots=None,
            init_vars=None,
            overrides={"resources": {}, "outputs_defaults": {}, "outputs": []},  # type: ignore[arg-type]
        )

    compilation = workflow_compile_mod.compile_workflow_ir(  # noqa: SLF001
        wf_obj,
        workflow_yaml_path=str(tmp_path / "wf.yaml"),
        path_aliases=None,
        template_vars=None,
        allowed_yaml_roots=None,
        init_vars=None,
        overrides=RunOverrides(),
    )
    assert compilation.workflow_ir.resources == ()
    assert compilation.demand_configs_by_run_id == {}


def test_resource_override_compile_output_extras_override_allows_none_cover_branches() -> None:
    assert resource_override_mod.compile_output_extras_override(None, path="p") == (None, None)  # noqa: SLF001


def test_resource_override_overlay_resources_override_rejects_invalid_file_id_key_cover_branches() -> None:
    override = ResourcesOverride(
        files={
            1: FileResourceOverride(kind="csv_file", path="./a.csv"),  # type: ignore[dict-item]
        }
    )

    with pytest.raises(ScalimWorkflowConfigError, match=r"p\.files keys must be non-empty strings") as exc_info:
        _ = resource_override_mod.overlay_resources_override(DemandConfig(), override, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.files"


def test_workflow_compile_compile_workflow_resources_rejects_duplicate_overrides_books_keys_after_strip_cover_branches(
    tmp_path: Path,
) -> None:
    wf_obj = WorkflowConfig(runs=(), resources=ResourcesConfig())
    override = ResourcesOverride(
        books={
            "report": BookResourceOverride(path="a"),
            " report ": BookResourceOverride(path="b"),
        }
    )

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.books has duplicate key: report") as exc_info:
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=tmp_path,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=override,
        )
    assert exc_info.value.path == "overrides.resources.books"


def test_workflow_compile_compile_workflow_resources_rejects_invalid_override_file_keys_cover_branches(tmp_path: Path) -> None:
    wf_obj = WorkflowConfig(runs=(), resources=ResourcesConfig())
    override = ResourcesOverride(
        files={
            1: FileResourceOverride(kind="csv_file", path="a"),  # type: ignore[dict-item]
        }
    )

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.files keys must be non-empty strings") as exc_info:
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=tmp_path,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=override,
        )
    assert exc_info.value.path == "overrides.resources.files"


def test_workflow_compile_compile_workflow_resources_rejects_duplicate_overrides_files_keys_after_strip_cover_branches(
    tmp_path: Path,
) -> None:
    wf_obj = WorkflowConfig(runs=(), resources=ResourcesConfig())
    override = ResourcesOverride(
        files={
            "detail_csv": FileResourceOverride(kind="csv_file", path="a"),
            " detail_csv ": FileResourceOverride(kind="csv_file", path="b"),
        }
    )

    with pytest.raises(ScalimWorkflowConfigError, match=r"overrides\.resources\.files has duplicate key: detail_csv") as exc_info:
        _ = workflow_compile_mod._compile_workflow_resources(  # noqa: SLF001
            wf_obj,
            workflow_base_dir=tmp_path,
            demand_cfg_by_run_id={},
            demand_yaml_paths_by_run_id={},
            init_vars=None,
            overrides_resources=override,
        )
    assert exc_info.value.path == "overrides.resources.files"
