import marimo

import importlib
from pathlib import Path
from typing import Any, Dict, Optional

from scalim import execution as api
from scalim.planning import PlanBuilder
from scalim.sinks import ColumnExcelSink, StreamingColumnExcelSink
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult
from scalim_misc.examples.public_api._fixtures import build_minimal_public_api_ir, build_minimal_public_api_runtime_bindings

__generated_with = "0.22.0"
app = marimo.App(width="full")
_EXAMPLE_ID = "example_public_api_suite/ch162_public_api_output_write_layout"

_run_ir_mod = importlib.import_module("scalim.execution.run_ir")


def run_public_api_output_write_layout(tmp_dir: Optional[Path] = None) -> ExampleResult:
    """演示 `OutputWriteLayout`：工厂选型 + 小 `IR` 写出（`HOLD` vs `WINDOW`）。

    按数据形状由调用方显式调优；默认不设 `layout` 时行为与历史一致。
    `YAML` `books` / `composition` 不能设列布局。
    """
    base = tmp_dir if tmp_dir is not None else Path(".tmp/examples/ch162_output_write_layout")
    base.mkdir(parents=True, exist_ok=True)

    demand_ir = build_minimal_public_api_ir()
    runtime_bindings = build_minimal_public_api_runtime_bindings()
    plan = PlanBuilder(demand_ir).build()
    layout = api.export_layout_from_demand_ir(demand_ir, plan.target_fields)

    hold_probe = base / "probe_hold.xlsx"
    win_probe = base / "probe_window.xlsx"
    hold_sink = _run_ir_mod._create_file_sink(
        api.OutputSpec(format="excel", path=str(hold_probe), streaming=False),
        layout,
        output_write_layout=api.OutputWriteLayout.COLUMN_HOLD,
    )
    win_sink = _run_ir_mod._create_file_sink(
        api.OutputSpec(format="excel", path=str(win_probe), streaming=False),
        layout,
        output_write_layout=api.OutputWriteLayout.COLUMN_WINDOW,
    )
    factory_ok = isinstance(hold_sink, ColumnExcelSink) and isinstance(win_sink, StreamingColumnExcelSink)
    hold_sink.close()
    # 未使用的 `WINDOW` `sink`：不调用 `close`（`close` 需要先 `set_row_ids`）

    hold_out = base / "run_hold.xlsx"
    win_out = base / "run_window.xlsx"
    for path in (hold_out, win_out):
        if path.exists():
            path.unlink()

    hold_result = api.run_ir(
        demand_ir,
        api.ExecutionRequest(
            export_layout=layout,
            output=api.OutputSpec(format="excel", path=str(hold_out), streaming=False, include_header=True),
            runtime_bindings=runtime_bindings,
            batch_size=10,
            output_write_layout=api.OutputWriteLayout.COLUMN_HOLD,
        ),
    )
    win_result = api.run_ir(
        demand_ir,
        api.ExecutionRequest(
            export_layout=layout,
            output=api.OutputSpec(format="excel", path=str(win_out), streaming=False, include_header=True),
            runtime_bindings=runtime_bindings,
            batch_size=10,
            output_write_layout=api.OutputWriteLayout.COLUMN_WINDOW,
        ),
    )

    derived = api.resolve_output_write_layout(
        output_write_layout=None,
        streaming=False,
        output_format="excel",
        excel_column_residency=api.ExcelColumnResidency.WINDOW,
        has_output_composition=False,
    )

    passed = bool(
        factory_ok
        and hold_result.total_rows == 3
        and win_result.total_rows == 3
        and hold_out.exists()
        and win_out.exists()
        and derived is api.OutputWriteLayout.COLUMN_WINDOW
    )
    details: Dict[str, Any] = {
        "factory_hold": type(hold_sink).__name__,
        "factory_window": type(win_sink).__name__,
        "hold_rows": hold_result.total_rows,
        "window_rows": win_result.total_rows,
        "derived_from_residency_window": derived.value,
        "syntax_hint": "DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)",
    }
    return ExampleResult(
        example_id=_EXAMPLE_ID,
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary="hold_rows={} window_rows={} factory_ok={}".format(hold_result.total_rows, win_result.total_rows, factory_ok),
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_public_api_output_write_layout()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch162_public_api_output_write_layout

        本章目标:
        - 演示 Python 调优旋钮 `OutputWriteLayout`（`row_stream` / `column_hold` / `column_window`）
        - 同 IR 下显式 HOLD vs WINDOW：工厂选型不同，行数一致
        - **不是**自动切换；YAML books / composition 不能设列布局

        推荐写法:
        ```python
        from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, OutputWriteLayout
        DemandRunRuntimeOptions(output_write_layout=OutputWriteLayout.COLUMN_WINDOW)
        ```
        迁移窗仍可用 `excel_column_residency=ExcelColumnResidency.WINDOW`（未设 layout 时等价推导）。

        SSOT:
        - `notebooks/marimo/example_public_api_suite/chapters/ch162_public_api_output_write_layout.py::run_public_api_output_write_layout`
        - 人类文档: `docs/doc/getting-started/excel-column-residency.md`
        - agent: `agentdev/skills/scalim-yaml-dsl/references/streaming-column-excel-guidance.md`

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
    result = run_public_api_output_write_layout()
    chapter_result = {
        "passed": result.passed,
        "summary": result.summary,
        "details": result.details if result.details is not None else {},
    }
    return (chapter_result,)


@app.cell(hide_code=True)
def _(mo, chapter_result):
    mo.callout(
        mo.md("## {}".format("PASS" if chapter_result["passed"] else "FAIL")),
        kind="success" if chapter_result["passed"] else "danger",
    )
    mo.md("```\n{}\n```".format(chapter_result["summary"]))
    return


@app.cell(hide_code=True)
def _(mo, chapter_result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(chapter_result["details"])
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
