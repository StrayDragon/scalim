import marimo

from typing import Any, Dict

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from notebooks.marimo.example_readme_suite.support.compare import run_compare

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_readme_suite/ch030_memory_compare"


def run_memory_compare_chapter() -> ExampleResult:
    try:
        summary: Dict[str, Any] = run_compare()
        naive = summary.get("naive") or {}
        scalim = summary.get("scalim") or {}
        passed = bool(int(naive.get("rows") or 0) == int(scalim.get("rows") or -1) and int(naive.get("rows") or 0) > 0)
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=str(
                {
                    "knobs": summary.get("knobs"),
                    "ratios": summary.get("ratios"),
                    "naive_rss_kb_delta": naive.get("rss_kb_delta"),
                    "scalim_rss_kb_delta": scalim.get("rss_kb_delta"),
                }
            ),
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
    return run_memory_compare_chapter()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_readme_suite / ch030_memory_compare

        用假数据比较全量读取和 Scalim 的内存变化。

        这里的数字是每次运行前后进程 RSS 的变化，不是运行中的最高内存。

        代码：`support/compare.py` / `naive_baseline.py` / `scalim_path.py` / `knobs.py`
        在仓库中可用 `just examples` 运行。
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
    from notebooks.marimo.example_readme_suite.support import knobs

    mo.ui.table(
        [
            {"knob": "N_ROWS", "value": knobs.N_ROWS},
            {"knob": "N_FIELDS", "value": knobs.N_FIELDS},
            {"knob": "BATCH_SIZE", "value": knobs.BATCH_SIZE},
            {"knob": "PAYLOAD_CHARS", "value": knobs.PAYLOAD_CHARS},
        ]
    )
    return


@app.cell
def _(mo):
    result = run_chapter()
    mo.md("**{}** — `{}`".format("PASS" if result.passed else "FAIL", result.summary))
    return (result,)


if __name__ == "__main__":
    app.run()
