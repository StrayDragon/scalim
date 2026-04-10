import marimo

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.execution import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.planning import PlanBuilder
from scalim.sinks import BlockColumnCSVSink, ColumnCSVSink
from scalim.sinks import InMemoryColumnSink
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")


def run_memory_optimization(
    cfg: Optional[ECommerceConfig] = None,
    *,
    batch_size: int = 10,
    write_delay: float = 0.0,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        demand = build_ecommerce_model(cfg)
        runtime_bindings = build_ecommerce_runtime_bindings()
        targets: List[str] = list(TARGET_FIELDS_FULL)
        plan = PlanBuilder(demand).build(targets=targets)

        observer_manager = ObserverManager()
        memory_observer = MemoryOptimizationObserver()
        observer_manager.register(memory_observer)

        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=runtime_bindings,
            observer_manager=observer_manager,
            batch_size=int(batch_size),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            col_csv = tmpdir_path / "column.csv"
            with ColumnCSVSink(str(col_csv), field_names=targets) as sink:
                engine.run(main_rows=None, sink=sink)

            # 用内存 `sink` 再跑一遍做对拍(避免解析 `CSV` 的类型损失)
            engine2 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=int(batch_size))
            with InMemoryColumnSink(field_names=targets) as mem_sink:
                engine2.run(main_rows=None, sink=mem_sink)
                results = mem_sink.get_rows()

            verification: VerificationResult = verify_scalim_output(results, fields_to_check=targets)

            # `BlockColumnCSVSink`: 仅用于演示,这里强制 `write_delay=0`,避免集成对拍变慢
            block_csv = tmpdir_path / "block.csv"
            engine3 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=int(batch_size))
            with BlockColumnCSVSink(str(block_csv), field_names=targets[:10], write_delay=float(write_delay)) as block_sink:
                engine3.run(main_rows=None, sink=block_sink)

        passed = bool(verification.passed and len(memory_observer.column_write_events) > 0)
        summary = "rows={} verify={} column_write_events={}".format(
            len(results), verification.passed, len(memory_observer.column_write_events)
        )
        if not verification.passed:
            summary = summary + "\n" + verification.summary

        details: Dict[str, Any] = {
            "rows": len(results),
            "verification": verification,
            "column_write_events": len(memory_observer.column_write_events),
            "field_slim_events": len(memory_observer.field_slim_events),
        }
        return ExampleResult(
            example_id="demo_big_data_report/ch050_memory_opt",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_memory_optimization()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch050_memory_opt

        本章目标:
        - 演示内存/写出相关优化路径的最小回归入口

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch050_memory_opt.py::run_memory_optimization`

        Gate:
        - `just examples`（跑全量）
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

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    from scalim_misc.demo_big_data_report.cases import build_test_config_small

    cfg = build_test_config_small()
    result = run_memory_optimization(cfg, batch_size=10, write_delay=0.0)
    return cfg, result


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
