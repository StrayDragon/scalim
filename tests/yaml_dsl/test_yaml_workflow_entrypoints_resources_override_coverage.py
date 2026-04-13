from pathlib import Path
from types import SimpleNamespace

import pytest

from scalim.dsl.yaml_dsl import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookWriteDefaultsOverride,
    BookResourceOverride,
    FileResourceOverride,
    ResourcesOverride,
    RunOptions,
    RunOverrides,
)
from scalim.dsl.yaml_dsl import workflow_entrypoints as entrypoints_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    FileConfig,
    ResourcesConfig,
)
from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, WorkflowOptions
from scalim.dsl.yaml_dsl.workflow_types import WorkflowRun, WorkflowRunOptionsPatch


def test_workflow_entrypoints_merge_book_override_helpers_cover_branches() -> None:
    left_budget = BookBudgetOverride(max_sheets=1, max_total_cells=2)
    right_budget = BookBudgetOverride(max_sheets=None, max_total_cells=3)
    assert entrypoints_mod._merge_book_budget_overrides(left_budget, None) == left_budget  # noqa: SLF001
    assert entrypoints_mod._merge_book_budget_overrides(None, right_budget) == right_budget  # noqa: SLF001
    merged_budget = entrypoints_mod._merge_book_budget_overrides(left_budget, right_budget)  # noqa: SLF001
    assert merged_budget is not None
    assert merged_budget.max_sheets == 1
    assert merged_budget.max_total_cells == 3

    left_export = BookExportXlsxOverride(path="a")
    right_export = BookExportXlsxOverride(path=None, allow_formulas=True)
    assert entrypoints_mod._merge_book_export_xlsx_overrides(left_export, None) == left_export  # noqa: SLF001
    assert entrypoints_mod._merge_book_export_xlsx_overrides(None, right_export) == right_export  # noqa: SLF001
    merged_export = entrypoints_mod._merge_book_export_xlsx_overrides(left_export, right_export)  # noqa: SLF001
    assert merged_export is not None
    assert merged_export.path == "a"
    assert merged_export.allow_formulas is True

    left_write = BookWriteDefaultsOverride(mode="append")
    right_write = BookWriteDefaultsOverride(mode=None, align_by="name")
    assert entrypoints_mod._merge_book_write_defaults_overrides(left_write, None) == left_write  # noqa: SLF001
    assert entrypoints_mod._merge_book_write_defaults_overrides(None, right_write) == right_write  # noqa: SLF001
    merged_write = entrypoints_mod._merge_book_write_defaults_overrides(left_write, right_write)  # noqa: SLF001
    assert merged_write is not None
    assert merged_write.mode == "append"
    assert merged_write.align_by == "name"

    left_book = BookResourceOverride(kind="xlsx_file", path="a", allow_formulas=True)
    right_book = BookResourceOverride(path="b", allow_formulas=None)
    assert entrypoints_mod._merge_book_resource_overrides(None, right_book) is right_book  # noqa: SLF001
    merged_book = entrypoints_mod._merge_book_resource_overrides(left_book, right_book)  # noqa: SLF001
    assert merged_book.kind == "xlsx_file"
    assert merged_book.path == "b"
    assert merged_book.allow_formulas is True

    left_file = FileResourceOverride(kind="csv_file", path="a", encoding="utf-8")
    right_file = FileResourceOverride(path="b")
    assert entrypoints_mod._merge_file_resource_overrides(None, right_file) is right_file  # noqa: SLF001
    merged_file = entrypoints_mod._merge_file_resource_overrides(left_file, right_file)  # noqa: SLF001
    assert merged_file.kind == "csv_file"
    assert merged_file.path == "b"
    assert merged_file.encoding == "utf-8"

    merged_resources = entrypoints_mod._merge_resources_overrides(  # noqa: SLF001
        ResourcesOverride(books={"report": left_book}),
        ResourcesOverride(books={"report": right_book}),
    )
    assert merged_resources is not None
    assert merged_resources.books is not None
    assert merged_resources.books["report"].path == "b"


def test_workflow_entrypoints_workflow_resources_override_handles_missing_and_converts() -> None:
    wf = WorkflowConfig(runs=(), options=WorkflowOptions(), resources="nope")  # type: ignore[arg-type]
    assert entrypoints_mod._workflow_resources_override(wf) is None  # noqa: SLF001

    wf_empty = WorkflowConfig(runs=(), options=WorkflowOptions(), resources=ResourcesConfig())
    assert entrypoints_mod._workflow_resources_override(wf_empty) is None  # noqa: SLF001

    wf2 = WorkflowConfig(
        runs=(),
        options=WorkflowOptions(),
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    kind="xlsx_file",
                    path="a",
                    allow_formulas=True,
                    write_defaults=BookWriteDefaultsConfig(mode="append"),
                ),
                "mem": BookConfig(
                    kind="xlsx_memory",
                    budget=BookBudgetConfig(max_sheets=1, max_total_cells=2),
                    export_xlsx=BookExportXlsxConfig(path="x", allow_formulas=True),
                ),
            },
            files={"detail_csv": FileConfig(kind="csv_file", path="a", encoding="utf-8")},
        ),
    )
    out = entrypoints_mod._workflow_resources_override(wf2)  # noqa: SLF001
    assert out is not None
    assert out.books is not None
    assert out.books["report"].allow_formulas is True
    assert out.books["report"].write_defaults is not None
    assert out.books["report"].write_defaults.mode == "append"
    assert out.books["mem"].budget is not None
    assert out.books["mem"].export_xlsx is not None
    assert out.books["mem"].export_xlsx.allow_formulas is True
    assert out.files is not None
    assert out.files["detail_csv"].encoding == "utf-8"


def test_workflow_entrypoints_merge_node_overrides_deep_merges_resources() -> None:
    workflow_resources_override = ResourcesOverride(
        files={"detail_csv": FileResourceOverride(kind="csv_file", path="wf", encoding="utf-8")}
    )
    base = RunOverrides(resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(path="a")}))

    merged = entrypoints_mod._merge_node_overrides(base, workflow_resources_override=workflow_resources_override)  # noqa: SLF001
    assert merged is not None
    assert merged.resources is not None
    assert merged.resources.files is not None
    assert merged.resources.files["detail_csv"].path == "a"
    assert merged.resources.files["detail_csv"].encoding == "utf-8"

    merged2 = entrypoints_mod._merge_node_overrides(None, workflow_resources_override=workflow_resources_override)  # noqa: SLF001
    assert merged2 is not None
    assert merged2.resources == workflow_resources_override

    same = entrypoints_mod._merge_node_overrides(base, workflow_resources_override=None)  # noqa: SLF001
    assert same is base


def test_workflow_entrypoints_lifecycle_skips_merge_when_patch_resources_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    wf = WorkflowConfig(
        runs=(
            WorkflowRun(id="r1", demand="d1.yaml"),
            WorkflowRun(id="r2", demand="d2.yaml"),
        ),
        options=WorkflowOptions(),
        resources=ResourcesConfig(),
    )

    def _fake_load_workflow_config_from_path(  # type: ignore[no-untyped-def]
        workflow_yaml_path: str,
        *,
        template_vars,
        template_sandbox,
        rendered_yaml_max_len,
    ):
        _ = (template_vars, template_sandbox, rendered_yaml_max_len)
        return Path(workflow_yaml_path), wf

    class _Stop(Exception):
        pass

    def _stop_compile(*_args: object, **_kwargs: object) -> object:
        raise _Stop()

    monkeypatch.setattr(entrypoints_mod, "load_workflow_config_from_path", _fake_load_workflow_config_from_path)
    monkeypatch.setattr(entrypoints_mod, "compile_workflow_ir", _stop_compile)

    base_options = RunOptions(allowed_modules=frozenset(["tests"]))
    patches = {"r1": WorkflowRunOptionsPatch(overrides=RunOverrides())}

    with pytest.raises(_Stop):
        entrypoints_mod.run_workflow_lifecycle_until_preflight(
            "wf.yaml",
            base_options=base_options,
            path_aliases=None,
            run_options_patches_by_run_id=patches,
            workflow_resources_wait=None,
            workflow_output_staging=None,
        )


def test_workflow_entrypoints_run_workflow_skips_bundle_viz_injection_when_patch_overrides_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_options = RunOptions(allowed_modules=frozenset(["tests"]))

    lifecycle = SimpleNamespace(
        parse=SimpleNamespace(workflow_yaml_path="wf.yaml"),
        preload=SimpleNamespace(
            workflow_ir=object(),
            cache_pool_logical_keys_by_node_id={},
            cache_pool_consumers_by_logical_key={},
        ),
        effective=SimpleNamespace(
            bundle_viz_base_config=None,
            options_by_run_id={"r1": base_options},
            run_options_patches_by_run_id={"r1": WorkflowRunOptionsPatch(overrides=None)},
        ),
    )
    monkeypatch.setattr(entrypoints_mod, "run_workflow_lifecycle_until_preflight", lambda *_a, **_k: lifecycle)

    class _Stop(Exception):
        pass

    captured: dict = {}

    def _fake_compile_demand_yaml(path: str, *, options: RunOptions):  # type: ignore[no-untyped-def]
        captured["path"] = path
        captured["options"] = options
        return object()

    def _fake_run_workflow_ir(  # type: ignore[no-untyped-def]
        workflow_path: str,
        workflow_ir: object,
        *,
        compile_demand_fn,
        **_kwargs,
    ) -> object:
        _ = (workflow_path, workflow_ir)
        _ = compile_demand_fn(
            "demand.yaml",
            workflow_exec_id="exec_0",
            workflow_node_id="r1",
            workflow_node_decl_order=0,
            node_init_vars={},
            managed_output_ids=None,
            viz_config=object(),
        )
        raise _Stop()

    monkeypatch.setattr(entrypoints_mod, "run_workflow_ir", _fake_run_workflow_ir)

    with pytest.raises(_Stop):
        entrypoints_mod.run_workflow(
            "wf.yaml",
            options=base_options,
            run_options_patches_by_run_id={"r1": WorkflowRunOptionsPatch(overrides=None)},
            compile_demand_yaml_fn=_fake_compile_demand_yaml,
        )

    assert captured["options"].overrides is None
