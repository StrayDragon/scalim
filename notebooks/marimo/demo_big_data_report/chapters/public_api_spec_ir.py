import marimo

from typing import Any, Dict

from scalim_misc.examples.public_api._coverage import (
    check_public_all_coverage,
    coverage_failure_summary,
    coverage_to_details,
)
from scalim.execution.run_ir import ExecutionRequest, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.sinks.sink_memory import InMemoryRowSink
from scalim.spec import ir as api
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir

__generated_with = "0.20.2"
app = marimo.App(width="full")

_COVERED_PUBLIC_ALL = {
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


def run_public_api_spec_ir() -> ExampleResult:
    coverage = check_public_all_coverage(api, covered=_COVERED_PUBLIC_ALL)
    if not coverage.ok:
        return ExampleResult(
            example_id="demo_big_data_report/public_api_spec_ir",
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary=coverage_failure_summary(coverage),
            details=coverage_to_details(coverage),
        )

    symbols = {name: getattr(api, name) for name in api.__all__}

    stable_lookup_keys = api.build_stable_lookup_key_list({("a", 2), ("a", 1), ("b", 1)})
    demand_ir = build_minimal_public_api_ir()
    export_layout = export_layout_from_demand_ir(
        demand_ir,
        ("item_id", "dim_id", "value_plus_one"),
        header_fields_output_by="field_id",
    )
    sink = InMemoryRowSink()
    request = ExecutionRequest(
        export_layout=export_layout,
        output=OutputSpec(path=None),
        sink=sink,
        output_composition=None,
        observability=None,
        guardrails=None,
        loader_retry=None,
        components=None,
        batch_size=10,
        parallel_mode="seq",
        max_workers=0,
    )
    core = run_ir(demand_ir, request)
    rows = sink.get_data()

    passed = bool(core.total_rows == len(rows) == 3 and rows and rows[0].get("value_plus_one") == 2)
    summary = "rows={} total_rows={} stable_lookup_keys={}".format(len(rows), core.total_rows, stable_lookup_keys)
    details: Dict[str, Any] = {
        "rows": rows,
        "stable_lookup_keys": stable_lookup_keys,
        "symbols_count": len(symbols),
    }
    return ExampleResult(
        example_id="demo_big_data_report/public_api_spec_ir",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_spec_ir()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / public_api_spec_ir

        本章目标:
        - 覆盖 `scalim.spec.ir.__all__` 的最小可运行示例
        - 演示 IR 构建 + `run_ir` 执行链路

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters/public_api_spec_ir.py::run_public_api_spec_ir`

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
    result = run_public_api_spec_ir()
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
