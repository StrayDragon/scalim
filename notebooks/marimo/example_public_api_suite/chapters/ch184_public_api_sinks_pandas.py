import marimo

from typing import Any, Dict, List

from scalim.sinks.pandas import PandasRowSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch184_public_api_sinks_pandas"


def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows:
        out: Dict[str, Any] = dict(row)
        if "id" in out and out["id"] is not None:
            out["id"] = int(out["id"])
        if "value" in out and out["value"] is not None:
            out["value"] = int(out["value"])
        normalized.append(out)
    return normalized


def run_public_api_sinks_pandas() -> ExampleResult:
    sink = PandasRowSink(field_names=["id", "value"])
    sink.write_batch([{"id": 1, "value": 10}, {"id": 2, "value": 20}])

    try:
        df = sink.to_dataframe()
    except ImportError as exc:
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary="missing optional dependency: pandas (context=scalim.sinks.pandas): {}".format(exc),
            details={"error": repr(exc)},
        )

    rows = _normalize_rows(df.to_dict(orient="records"))
    passed = bool(rows == [{"id": 1, "value": 10}, {"id": 2, "value": 20}] and list(df.columns) == ["id", "value"])
    summary = "rows={} columns={}".format(len(rows), ",".join([str(c) for c in df.columns]))
    details: Dict[str, Any] = {"rows": rows}
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_sinks_pandas()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch184_public_api_sinks_pandas

        本章目标:
        - 演示可选依赖入口: `scalim.sinks.pandas`
        - 在缺失 `pandas` 依赖时 fail-fast 给出明确提示

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch184_public_api_sinks_pandas.py::run_public_api_sinks_pandas`

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
    result = run_public_api_sinks_pandas()
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
