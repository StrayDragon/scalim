"""Cells-native marimo notebook: ch130_public_api_dsl_by_yaml.

迁移对照:
  Before: 模块级 run_public_api_dsl_by_yaml() 持全部逻辑;cells 薄壳 +
          自引用 chapter_result 残留 bug
  After:  public __all__ 触达 / compile/run / workflow / duplicate headers 全部在 cells 内
"""

import marimo

from typing import Any, Dict, FrozenSet, Optional, Set

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "example_public_api_suite/ch130_public_api_dsl_by_yaml"


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch130_public_api_dsl_by_yaml

        本章目标:
        - 最小可运行示例: `compile/run/run_workflow` + overrides + allowlist
        - 覆盖稳定入口的基础可用性: 相关模块可 import 且其 `__all__` 可解析

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：`write_text` / `write_duplicate_headers_workflow_fixture` / `touch_public_all`
        2. 触达 7 个模块的 public `__all__`
        3. demand: `compile` → `run`（CaptureRows）
        4. workflow: batch_size 观察 + patch（r1=5 / r2=2）+ preload 断言
        5. duplicate headers 对照（global 配置 vs run patch）
        6. 断言展开 → chapter_result

        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Any, Dict, FrozenSet, Optional, Set

    from scalim.dsl import yaml_dsl as api
    from scalim_misc.examples.public_api._fixtures import get_preload_counter_calls, reset_preload_counter_calls
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        Dict,
        FrozenSet,
        Optional,
        Path,
        Set,
        api,
        get_preload_counter_calls,
        make_chapter_result,
        render_checks,
        reset_preload_counter_calls,
        tempfile,
    )


@app.cell
def _(Any, Dict, Path, api):
    # 零件: 文本写入 / duplicate headers fixture / public __all__ 触达
    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def write_duplicate_headers_workflow_fixture(tmp: Path) -> Path:
        demand_path = tmp / "duplicate_headers.demand.yaml"
        workflow_path = tmp / "duplicate_headers.workflow.yaml"
        output_root = tmp / "duplicate_headers_out"

        demand_lines = [
            "name: public_api_duplicate_headers",
            "",
            "main_source:",
            "  source_id: items",
            '  loader: "scalim_misc.examples.public_api._fixtures:load_items"',
            "  fields:",
            "    item_id: {extract: item_id, name: Dup}",
            "    dim_id: {extract: dim_id, name: Dup}",
            "",
            "sources: {}",
            "",
            "resources:",
            "  files:",
            "    detail_csv:",
            "      csv_file:",
            '        path: "%s"' % str(output_root),
            "",
            "outputs:",
            "  - name: detail",
            "    to: {file: detail_csv}",
            "    fields: [item_id, dim_id]",
        ]
        write_text(demand_path, "\n".join(demand_lines))
        workflow_lines = [
            "workflow:",
            "  runs:",
            "    - id: dup",
            "      demand: duplicate_headers.demand.yaml",
        ]
        write_text(workflow_path, "\n".join(workflow_lines))
        return workflow_path

    def touch_public_all(module: Any) -> int:
        declared_all = getattr(module, "__all__", ())
        for name in declared_all:
            getattr(module, name)
        return len(declared_all)

    return touch_public_all, write_duplicate_headers_workflow_fixture, write_text


@app.cell
def _(Any, Dict, FrozenSet, Path, api, tempfile, touch_public_all):
    import atexit
    import shutil

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])

    # 触达 7 个模块的 public __all__
    from scalim.dsl.yaml_dsl import tools as tools_api
    from scalim.dsl.yaml_dsl import workflow as workflow_api
    from scalim.dsl.yaml_dsl import workflow_paths as workflow_paths_api
    from scalim.dsl.yaml_dsl import workflow_types as workflow_types_api
    from scalim.events import EventType, WORKFLOW_NODE_ID_META_KEY
    from scalim.ob.observer import Observer
    from scalim.spec import ir as spec_ir_api
    from scalim.workflow import loaders as workflow_loaders_api

    all_touched: Dict[str, Any] = {}
    for mod in (api, tools_api, workflow_api, workflow_paths_api, workflow_types_api, spec_ir_api, workflow_loaders_api):
        all_touched[str(getattr(mod, "__name__", type(mod).__name__))] = touch_public_all(mod)

    symbols = {name: getattr(api, name) for name in api.__all__}
    _ = symbols.get("UNSET")
    print("touched public __all__:", all_touched)

    tmp = Path(tempfile.mkdtemp(prefix="scalim-pubapi-130-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    print("tmp dir:", tmp)

    return (
        ALLOWED_MODULES,
        EventType,
        Observer,
        WORKFLOW_NODE_ID_META_KEY,
        all_touched,
        spec_ir_api,
        symbols,
        tmp,
        tools_api,
        workflow_api,
        workflow_loaders_api,
        workflow_paths_api,
        workflow_types_api,
    )


@app.cell
def _(EventType, Observer, Optional, Set, WORKFLOW_NODE_ID_META_KEY, api):
    # 零件: 观察 workflow 各 node 的实际 batch_size
    class WorkflowBatchSizeObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.PIPELINE_START}
            self.batch_size_by_workflow_node_id: Dict[str, Optional[int]] = {}

        def on_event(self, event: Any) -> None:
            if getattr(event, "event_type", None) != EventType.PIPELINE_START:
                return
            meta = getattr(event, "meta", None) or {}
            raw_node_id = meta.get(WORKFLOW_NODE_ID_META_KEY)
            if not raw_node_id:
                return
            payload = getattr(event, "payload", None)
            batch_size = getattr(payload, "batch_size", None)
            self.batch_size_by_workflow_node_id[str(raw_node_id)] = None if batch_size is None else int(batch_size)

    return WorkflowBatchSizeObserver


@app.cell
def _(ALLOWED_MODULES, Path, write_duplicate_headers_workflow_fixture, write_text, api, tmp, tools_api):
    # demand YAML + compile + run
    demand_path = tmp / "demand.yaml"
    workflow_path = tmp / "workflow.yaml"
    duplicate_workflow_path = write_duplicate_headers_workflow_fixture(tmp)

    demand_yaml = "\n".join([
        "name: public_api_minimal_demand",
        "",
        "main_source:",
        '  source_id: items',
        '  loader: "scalim_misc.examples.public_api._fixtures:load_items"',
        "  fields:",
        "    item_id: {extract: item_id, name: Item ID}",
        "    dim_id: {extract: dim_id, name: Dim ID}",
        "",
        "sources:",
        "  dims:",
        '    loader: "scalim_misc.examples.public_api._fixtures:load_dims"',
        "    key: dim_id",
        "    cache_mode: preload_forever",
    ])
    write_text(demand_path, demand_yaml)

    workflow_yaml = "\n".join([
        "workflow:",
        "  runs:",
        "    - id: r1",
        "      demand: demand.yaml",
        "    - id: r2",
        "      demand: demand.yaml",
    ])
    write_text(workflow_path, workflow_yaml)

    init_vars = {"order_ids": []}
    tools_output_config = tools_api.load_output_config(str(demand_path))
    base_module_path = tools_api.derive_base_module_path(str(demand_path), sys_path=[str(tmp)], cwd=str(tmp))

    compilation: api.Compilation = api.compile(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=api.DemandRunTemplateOptions(init_vars=init_vars),
            runtime=api.DemandRunRuntimeOptions(batch_size=2),
        ),
    )
    print("compile OK, fields =", len(compilation.demand_ir.fields))

    overrides = api.RunOverrides.csv_file(
        output_root=str(tmp / "out"),
        fields=["item_id", "dim_id"],
        header_fields_output_by="name",
    )
    run_result: api.DemandRunResult = api.run(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=api.DemandRunTemplateOptions(init_vars=init_vars),
            runtime=api.DemandRunRuntimeOptions(batch_size=2),
            outputs=api.DemandRunOutputOptions(overrides=overrides, capture=api.CaptureRows()),
        ),
    )
    captured_rows = run_result.captured_rows
    rows = [] if captured_rows is None else list(captured_rows.iter_row_data())
    print("run rows =", len(rows), "total_rows =", run_result.total_rows)

    return (
        base_module_path,
        compilation,
        demand_path,
        duplicate_workflow_path,
        init_vars,
        overrides,
        rows,
        run_result,
        tools_output_config,
        workflow_path,
    )


@app.cell
def _(ALLOWED_MODULES, WorkflowBatchSizeObserver, api, get_preload_counter_calls, init_vars, reset_preload_counter_calls, workflow_path, workflow_types_api):
    # workflow 运行 + patch + preload 断言
    reset_preload_counter_calls()
    workflow_batch_size_observer = WorkflowBatchSizeObserver()
    workflow_runtime_options = workflow_types_api.WorkflowRuntimeOptions(
        execution=workflow_types_api.WorkflowExecutionOptions(max_concurrency=2, failure_policy="all_fail"),
        cache_pool=workflow_types_api.WorkflowCachePoolPreloadForeverShared(max_entries=16),
    )
    wf = api.run_workflow(
        str(workflow_path),
        options=workflow_types_api.WorkflowRunOptions(
            demand=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                template=api.DemandRunTemplateOptions(init_vars=init_vars),
                runtime=api.DemandRunRuntimeOptions(
                    components=[workflow_batch_size_observer],
                    batch_size=2,
                    max_workers=0,
                ),
            ),
            runtime=workflow_runtime_options,
            patches_by_run_id={"r1": workflow_types_api.WorkflowNodePatch(batch_size=5)},
        ),
    )
    workflow_batch_sizes = dict(workflow_batch_size_observer.batch_size_by_workflow_node_id)
    preload_calls = get_preload_counter_calls()
    errors = wf.errors()
    print("outcomes =", [o.run_id for o in wf.outcomes])
    print("batch_sizes =", workflow_batch_sizes)
    print("preload_calls =", preload_calls, "errors =", len(errors))
    return errors, preload_calls, wf, workflow_batch_sizes


@app.cell
def _(ALLOWED_MODULES, api, duplicate_workflow_path, tmp, workflow_types_api):
    from scalim.shortcuts.resources import outputs

    # duplicate headers 对照: global 配置 vs run patch
    duplicate_global = api.run_workflow(
        str(duplicate_workflow_path),
        options=workflow_types_api.WorkflowRunOptions(
            demand=api.DemandRunOptions(
                security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
                runtime=api.DemandRunRuntimeOptions(
                    demand_diagnostics=api.DemandDiagnosticsPolicy(validate_unique_field_names=False),
                ),
            ),
        ),
    )
    duplicate_patch = api.run_workflow(
        str(duplicate_workflow_path),
        options=workflow_types_api.WorkflowRunOptions(
            demand=api.DemandRunOptions(security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES)),
            patches_by_run_id={
                "dup": workflow_types_api.WorkflowNodePatch(
                    demand_diagnostics=api.DemandDiagnosticsOverride(validate_unique_field_names=False),
                )
            },
        ),
    )
    duplicate_global_errors = duplicate_global.errors()
    duplicate_patch_errors = duplicate_patch.errors()
    try:
        dup_root = tmp / "duplicate_headers_out"
        latest = outputs.load_latest_outputs(dup_root)
        detail_csv = latest.files.get("detail_csv")
        duplicate_output_exists = bool(detail_csv and detail_csv.exists())
    except Exception:  # noqa: BLE001
        duplicate_output_exists = False
    print("dup_global_errors =", len(duplicate_global_errors), "dup_patch_errors =", len(duplicate_patch_errors))
    return (
        duplicate_global,
        duplicate_global_errors,
        duplicate_output_exists,
        duplicate_patch,
        duplicate_patch_errors,
    )


@app.cell
def _(duplicate_global_errors, duplicate_output_exists, duplicate_patch_errors, errors, preload_calls, render_checks, rows, wf, workflow_batch_sizes):
    checks = {
        "无 workflow errors": not errors,
        "preload 仅 1 次": preload_calls == 1,
        "r1 batch_size == 5 (patch)": workflow_batch_sizes.get("r1") == 5,
        "r2 batch_size == 2": workflow_batch_sizes.get("r2") == 2,
        "首行 item_id == 1": bool(rows) and rows[0].get("item_id") == 1,
        "duplicate headers 对照全过": not duplicate_global_errors and not duplicate_patch_errors and duplicate_output_exists,
        "workflow outcomes == [r1, r2]": len(wf.outcomes) == 2 and [o.run_id for o in wf.outcomes] == ["r1", "r2"],
    }
    render_checks(checks)
    return checks


@app.cell
def _(all_touched, base_module_path, checks, duplicate_global, duplicate_global_errors, duplicate_output_exists, duplicate_patch, duplicate_patch_errors, errors, make_chapter_result, preload_calls, rows, run_result, tools_output_config, wf, workflow_batch_sizes):
    passed = bool(all(checks.values()))
    summary = "rows={} workflow_outcomes={} preload_calls={} batch_sizes={} errors={} duplicate_global_errors={} duplicate_patch_errors={}".format(
        len(rows),
        len(wf.outcomes),
        preload_calls,
        workflow_batch_sizes,
        len(errors),
        len(duplicate_global_errors),
        len(duplicate_patch_errors),
    )
    if errors:
        summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)
    if duplicate_global_errors:
        summary = summary + "\nduplicate_global_first_error: {} {}".format(
            duplicate_global_errors[0].exc_type,
            duplicate_global_errors[0].message,
        )
    if duplicate_patch_errors:
        summary = summary + "\nduplicate_patch_first_error: {} {}".format(
            duplicate_patch_errors[0].exc_type,
            duplicate_patch_errors[0].message,
        )

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "rows": len(rows),
            "run_total_rows": int(run_result.total_rows),
            "workflow_outcomes": wf.outcomes,
            "workflow_batch_sizes": workflow_batch_sizes,
            "preload_calls": preload_calls,
            "errors": errors,
            "duplicate_global_outcomes": duplicate_global.outcomes,
            "duplicate_global_errors": duplicate_global_errors,
            "duplicate_patch_outcomes": duplicate_patch.outcomes,
            "duplicate_patch_errors": duplicate_patch_errors,
            "duplicate_output_exists": duplicate_output_exists,
            "touched_public_all": all_touched,
            "tools": {"base_module_path": base_module_path, "output_fields": tools_output_config.get("output_fields")},
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()