import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet

from notebooks.marimo._support.public_api import (
    check_public_all_coverage,
    coverage_failure_summary,
    coverage_to_details,
)
from scalim.dsl import by_yaml as api
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import get_preload_counter_calls, reset_preload_counter_calls

__generated_with = "0.20.2"
app = marimo.App(width="full")

_COVERED_PUBLIC_ALL = {
    "UNSET",
    "Compilation",
    "OutputOverrides",
    "RunOptions",
    "RunOverrides",
    "RunResult",
    "compile",
    "run",
    "run_workflow",
}

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXPECTED_WORKFLOW_RUNS = 2


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_public_api_dsl_by_yaml() -> ExampleResult:
    coverage = check_public_all_coverage(api, covered=_COVERED_PUBLIC_ALL)
    if not coverage.ok:
        return ExampleResult(
            example_id="demo_big_data_report/public_api_dsl_by_yaml",
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary=coverage_failure_summary(coverage),
            details=coverage_to_details(coverage),
        )

    symbols = {name: getattr(api, name) for name in api.__all__}
    _ = symbols.get("UNSET")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = tmp / "demand.yaml"
        workflow_path = tmp / "workflow.yaml"

        demand_yaml = """\
name: public_api_minimal_demand
batch_size: 2

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
    share_preload_cache: true
"""
        _write_text(workflow_path, workflow_yaml)

        runtime_vars = {"order_ids": []}

        compilation: api.Compilation = api.compile(str(demand_path), allowed_modules=_ALLOWED_MODULES, runtime_vars=runtime_vars)
        if not compilation.demand_ir.fields:
            return ExampleResult(
                example_id="demo_big_data_report/public_api_dsl_by_yaml",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile returned empty IR",
                details={"demand_ir_fields": len(compilation.demand_ir.fields)},
            )

        sink = InMemoryRowSink()
        overrides = api.RunOverrides(output=api.OutputOverrides(path=None, include_header=api.UNSET))
        run_result: api.RunResult = api.run(
            str(demand_path),
            allowed_modules=_ALLOWED_MODULES,
            sink=sink,
            overrides=overrides,
            runtime_vars=runtime_vars,
        )
        rows = sink.get_data()
        if not rows:
            return ExampleResult(
                example_id="demo_big_data_report/public_api_dsl_by_yaml",
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="run produced no rows",
                details={"run_result": run_result},
            )

        options = api.RunOptions(
            allowed_modules=_ALLOWED_MODULES,
            runtime_vars=runtime_vars,
            overrides=overrides,
        )
        _ = options.parallel_mode

        reset_preload_counter_calls()
        wf = api.run_workflow(
            str(workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            max_workers=0,
            runtime_vars=runtime_vars,
        )
        preload_calls = get_preload_counter_calls()
        errors = wf.errors()
        passed = bool(
            not errors
            and preload_calls == 1
            and len(wf.outcomes) == _EXPECTED_WORKFLOW_RUNS
            and [o.run_id for o in wf.outcomes] == ["r1", "r2"]
            and rows[0].get("item_id") == 1
        )
        summary = "rows={} workflow_outcomes={} preload_calls={} errors={}".format(len(rows), len(wf.outcomes), preload_calls, len(errors))
        if errors:
            summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

        details: Dict[str, Any] = {
            "rows": len(rows),
            "run_total_rows": int(run_result.total_rows),
            "workflow_outcomes": wf.outcomes,
            "preload_calls": preload_calls,
            "errors": errors,
        }
        return ExampleResult(
            example_id="demo_big_data_report/public_api_dsl_by_yaml",
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
        # demo_big_data_report / public_api_dsl_by_yaml

        本章目标:
        - 覆盖 `scalim.dsl.by_yaml.__all__` 的最小可运行示例
        - 演示 `compile/run/run_workflow` + overrides + allowlist

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/public_api_dsl_by_yaml.py::run_public_api_dsl_by_yaml`

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
