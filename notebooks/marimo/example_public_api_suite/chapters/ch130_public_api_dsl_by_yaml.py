import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, FrozenSet

from scalim_misc.examples.public_api._coverage import (
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
    "ResolverTrustedMode",
    "RunOverrides",
    "RunResult",
    "compile",
    "run",
    "run_workflow",
}

_COVERED_WORKFLOW_ALL = {
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowConfigError",
    "WorkflowOptions",
    "WorkflowResources",
    "WorkflowRun",
    "WorkflowWriteTo",
    "WorkflowWriteToCsvAppend",
    "WorkflowWriteToSheetbookAppend",
    "WorkflowWriteToSheetbookSheet",
    "WorkflowWriteToWorkbookAppend",
    "WorkflowWriteToWorkbookSheet",
    "load_workflow_config",
    "load_workflow_config_from_mapping",
    "resolve_workflow_demand_path",
    "validate_workflow_yaml_text_json",
}

_COVERED_WORKFLOW_TYPES_ALL = {
    "WorkflowCachePoolBudget",
    "WorkflowCachePoolOptions",
    "WorkflowCachePoolPin",
    "WorkflowConfig",
    "WorkflowConfigError",
    "WorkflowOptions",
    "WorkflowResources",
    "WorkflowRun",
    "WorkflowWriteTo",
    "WorkflowWriteToCsvAppend",
    "WorkflowWriteToSheetbookAppend",
    "WorkflowWriteToSheetbookSheet",
    "WorkflowWriteToWorkbookAppend",
    "WorkflowWriteToWorkbookSheet",
}

_COVERED_WORKFLOW_PATHS_ALL = {
    "resolve_workflow_demand_path",
}

_COVERED_SPEC_IR_ALL = {
    "BindingIr",
    "ComputeCallContextIr",
    "CsvFieldPresentationIr",
    "DemandIr",
    "DerivedFieldIr",
    "ExportProfileIr",
    "FieldIr",
    "FieldPresentationIr",
    "FieldRefIr",
    "JoinConditionIr",
    "KeyIr",
    "LoaderCallContextIr",
    "LoaderExtractor",
    "LoaderIr",
    "LoaderParamsBuilder",
    "LoaderResultMapCallable",
    "LookupKeyCast",
    "LookupKeySpec",
    "LookupStepIr",
    "MainSourceIr",
    "MainSourceRowIterableCallable",
    "NormalizedLookupKeySpec",
    "OrderByKeyIr",
    "PandasFieldPresentationIr",
    "RelationIr",
    "SourceIr",
    "SourceNormalizeIr",
    "SourceRefIr",
    "SpreadsheetFieldPresentationIr",
    "SupportedFieldIr",
    "build_stable_lookup_key_list",
}

_COVERED_WORKFLOW_LOADERS_ALL = {
    "sheetbook_sheet_rows",
    "workflow_loader_context",
}

_ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])
_EXPECTED_WORKFLOW_RUNS = 2
_EXAMPLE_ID = "example_public_api_suite/ch130_public_api_dsl_by_yaml"


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def run_public_api_dsl_by_yaml() -> ExampleResult:
    coverage = check_public_all_coverage(api, covered=_COVERED_PUBLIC_ALL)
    if not coverage.ok:
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary=coverage_failure_summary(coverage),
            details=coverage_to_details(coverage),
        )

    from scalim.dsl.by_yaml import workflow as workflow_api
    from scalim.dsl.by_yaml import workflow_paths as workflow_paths_api
    from scalim.dsl.by_yaml import workflow_types as workflow_types_api
    from scalim.spec import ir as spec_ir_api
    from scalim.workflow import loaders as workflow_loaders_api

    for mod, covered in (
        (workflow_api, _COVERED_WORKFLOW_ALL),
        (workflow_types_api, _COVERED_WORKFLOW_TYPES_ALL),
        (workflow_paths_api, _COVERED_WORKFLOW_PATHS_ALL),
        (spec_ir_api, _COVERED_SPEC_IR_ALL),
        (workflow_loaders_api, _COVERED_WORKFLOW_LOADERS_ALL),
    ):
        mod_coverage = check_public_all_coverage(mod, covered=covered)
        if not mod_coverage.ok:
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary=coverage_failure_summary(mod_coverage),
                details=coverage_to_details(mod_coverage),
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
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 16
        over_budget_policy: fail_fast
"""
        _write_text(workflow_path, workflow_yaml)

        init_vars = {"order_ids": []}

        compilation: api.Compilation = api.compile(str(demand_path), allowed_modules=_ALLOWED_MODULES, init_vars=init_vars)
        if not compilation.demand_ir.fields:
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile returned empty IR",
                details={"demand_ir_fields": len(compilation.demand_ir.fields)},
            )

        sink = InMemoryRowSink()
        overrides = api.RunOverrides(
            outputs=[
                {
                    "name": "detail",
                    "container": {
                        "type": "csv",
                        "path": str(tmp / "out.csv"),
                        "include_header": True,
                        "header_fields_output_by": "name",
                        "streaming": True,
                    },
                    "fields": ["item_id", "dim_id"],
                }
            ]
        )
        run_result: api.RunResult = api.run(
            str(demand_path),
            allowed_modules=_ALLOWED_MODULES,
            sink=sink,
            overrides=overrides,
            init_vars=init_vars,
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
        wf = api.run_workflow(
            str(workflow_path),
            allowed_modules=_ALLOWED_MODULES,
            max_workers=0,
            init_vars=init_vars,
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
        - 覆盖 `scalim.dsl.by_yaml.__all__` 的最小可运行示例
        - 演示 `compile/run/run_workflow` + overrides + allowlist
        - 覆盖 curated public entrypoints: workflow helpers / `scalim.spec.ir` / `scalim.workflow.loaders`

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
