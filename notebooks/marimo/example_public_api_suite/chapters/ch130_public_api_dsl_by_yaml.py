import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional, Set

from scalim.dsl import by_yaml as api
from scalim.sinks import InMemoryRowSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import get_preload_counter_calls, reset_preload_counter_calls

__generated_with = "0.20.2"
app = marimo.App(width="full")

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXPECTED_WORKFLOW_RUNS = 2
_EXAMPLE_ID = "example_public_api_suite/ch130_public_api_dsl_by_yaml"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_duplicate_headers_workflow_fixture(tmp: Path) -> Path:
    demand_path = tmp / "duplicate_headers.demand.yaml"
    workflow_path = tmp / "duplicate_headers.workflow.yaml"
    output_path = tmp / "duplicate_headers.csv"

    _write_text(
        demand_path,
        """\
name: public_api_duplicate_headers

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items"
  fields:
    item_id: {extract: item_id, name: Dup}
    dim_id: {extract: dim_id, name: Dup}

sources: {}

resources:
  files:
    detail_csv:
      kind: csv_file
      path: "%s"

outputs:
  - name: detail
    to: {file: detail_csv}
    fields: [item_id, dim_id]
"""
        % str(output_path),
    )
    _write_text(
        workflow_path,
        """\
workflow:
  runs:
    - id: dup
      demand: duplicate_headers.demand.yaml
  options:
    max_concurrency: 1
    failure_policy: primary_only
""",
    )
    return workflow_path


def _touch_public_all(module: Any) -> int:
    declared_all = getattr(module, "__all__", ())
    for name in declared_all:
        getattr(module, name)
    return len(declared_all)


def run_public_api_dsl_by_yaml() -> ExampleResult:
    from scalim.dsl.by_yaml import tools as tools_api
    from scalim.dsl.by_yaml import workflow as workflow_api
    from scalim.dsl.by_yaml import workflow_paths as workflow_paths_api
    from scalim.dsl.by_yaml import workflow_types as workflow_types_api
    from scalim.events import EVENT_PIPELINE_START, WORKFLOW_NODE_ID_META_KEY
    from scalim.ob.observer import Observer
    from scalim.spec import ir as spec_ir_api
    from scalim.workflow import loaders as workflow_loaders_api

    all_touched: Dict[str, Any] = {}
    for mod in (api, tools_api, workflow_api, workflow_paths_api, workflow_types_api, spec_ir_api, workflow_loaders_api):
        try:
            all_touched[str(getattr(mod, "__name__", type(mod).__name__))] = _touch_public_all(mod)
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="public __all__ 解析失败: {}: {} {}".format(
                    getattr(mod, "__name__", type(mod).__name__),
                    type(exc).__name__,
                    exc,
                ),
                details={"module": getattr(mod, "__name__", type(mod).__name__), "exc_type": type(exc).__name__, "message": str(exc)},
            )

    symbols = {name: getattr(api, name) for name in api.__all__}
    _ = symbols.get("UNSET")

    class _WorkflowBatchSizeObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[str]] = {EVENT_PIPELINE_START}
            self.batch_size_by_workflow_node_id: Dict[str, Optional[int]] = {}

        def on_event(self, event: Any) -> None:
            if getattr(event, "event_type", None) != EVENT_PIPELINE_START:
                return
            meta = getattr(event, "meta", None) or {}
            raw_node_id = meta.get(WORKFLOW_NODE_ID_META_KEY)
            if not raw_node_id:
                return
            payload = getattr(event, "payload", None)
            batch_size = getattr(payload, "batch_size", None)
            self.batch_size_by_workflow_node_id[str(raw_node_id)] = None if batch_size is None else int(batch_size)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        workflow_path = tmp / "workflow.yaml"
        duplicate_workflow_path = _write_duplicate_headers_workflow_fixture(tmp)

        demand_yaml = """\
name: public_api_minimal_demand

main_source:
  source_id: items
  loader: "scalim_misc.examples.public_api._fixtures:load_items"
  fields:
    item_id: {extract: item_id, name: Item ID}
    dim_id: {extract: dim_id, name: Dim ID}

sources:
  dims:
    loader: "scalim_misc.examples.public_api._fixtures:load_dims"
    key: dim_id
    cache_mode: preload_forever
"""
        _write_text(demand_path, demand_yaml)

        workflow_yaml = """\
workflow:
  runs:
    - id: r1
      demand: demand.yaml
    - id: r2
      demand: demand.yaml
  options:
    max_concurrency: 2
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 16
        over_budget_policy: fail_fast
"""
        _write_text(workflow_path, workflow_yaml)

        init_vars = {"order_ids": []}

        tools_output_config = tools_api.load_output_config(str(demand_path))
        base_module_path = tools_api.derive_base_module_path(str(demand_path), sys_path=[str(tmp)], cwd=str(tmp))

        compilation: api.Compilation = api.compile(
            str(demand_path),
            options=api.RunOptions(
                allowed_modules=_ALLOWED_MODULES,
                init_vars=init_vars,
                batch_size=2,
            ),
        )
        if not compilation.demand_ir.fields:
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile returned empty IR",
                details={"demand_ir_fields": len(compilation.demand_ir.fields)},
            )

        sink = InMemoryRowSink()
        overrides = api.RunOverrides.csv_file(
            output_path=str(tmp / "out.csv"),
            fields=["item_id", "dim_id"],
            header_fields_output_by="name",
        )
        run_result: api.RunResult = api.run(
            str(demand_path),
            options=api.RunOptions(
                allowed_modules=_ALLOWED_MODULES,
                sink=sink,
                overrides=overrides,
                init_vars=init_vars,
                batch_size=2,
            ),
        )
        rows = sink.get_data()
        if not rows:
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="run produced no rows",
                details={"run_result": run_result},
            )

        reset_preload_counter_calls()
        workflow_batch_size_observer = _WorkflowBatchSizeObserver()
        wf = api.run_workflow(
            str(workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            components=[workflow_batch_size_observer],
            max_workers=0,
            init_vars=init_vars,
            batch_size=2,
            run_patches_by_id={
                "r1": workflow_types_api.WorkflowRunPatch(batch_size=5),
            },
        )
        workflow_batch_sizes = dict(workflow_batch_size_observer.batch_size_by_workflow_node_id)
        preload_calls = get_preload_counter_calls()
        errors = wf.errors()
        duplicate_global = api.run_workflow(
            str(duplicate_workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            demand_diagnostics=api.DemandDiagnosticsPolicy(validate_unique_field_names=False),
        )
        duplicate_patch = api.run_workflow(
            str(duplicate_workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            run_patches_by_id={
                "dup": workflow_types_api.WorkflowRunPatch(
                    demand_diagnostics=api.DemandDiagnosticsOverride(validate_unique_field_names=False)
                )
            },
        )
        duplicate_global_errors = duplicate_global.errors()
        duplicate_patch_errors = duplicate_patch.errors()
        duplicate_output_exists = (tmp / "duplicate_headers.csv").exists()
        passed = bool(
            not errors
            and not duplicate_global_errors
            and not duplicate_patch_errors
            and duplicate_output_exists
            and preload_calls == 1
            and len(wf.outcomes) == _EXPECTED_WORKFLOW_RUNS
            and [o.run_id for o in wf.outcomes] == ["r1", "r2"]
            and workflow_batch_sizes.get("r1") == 5
            and workflow_batch_sizes.get("r2") == 2
            and rows[0].get("item_id") == 1
        )
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

        details: Dict[str, Any] = {
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
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_public_api_dsl_by_yaml()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch130_public_api_dsl_by_yaml

        本章目标:
        - 最小可运行示例: `compile/run/run_workflow` + overrides + allowlist
        - 覆盖稳定入口的基础可用性: 相关模块可 import 且其 `__all__` 可解析

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch130_public_api_dsl_by_yaml.py::run_public_api_dsl_by_yaml`

        Gate:
        - `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    result = run_public_api_dsl_by_yaml()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
