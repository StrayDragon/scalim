import marimo

from typing import Any, Dict

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from notebooks.marimo.example_readme_suite.support.min_python import run_min_python

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_readme_suite/ch010_min_python"


def run_min_python_chapter() -> ExampleResult:
    try:
        summary: Dict[str, Any] = run_min_python()
        passed = bool(int(summary.get("rows") or 0) == 3)
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=str(summary),
            details=summary,
        )
    except Exception as exc:  # noqa: BLE001
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary="{}: {}".format(type(exc).__name__, exc),
            details={"exc_type": type(exc).__name__, "message": str(exc)},
        )


def run_chapter() -> ExampleResult:
    return run_min_python_chapter()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch010_min_python

        最小可跑 Python IR（假数据闭环）。

        SSOT: `support/min_python.py::run_min_python`  
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
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _(mo):
    result = run_chapter()
    mo.md("**{}** — `{}`".format("PASS" if result.passed else "FAIL", result.summary))
    return (result,)


if __name__ == "__main__":
    app.run()
