"""Cells-native: ch050_memory_opt — memory optimization observer + block column CSV."""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Memory Optimization Observer + BlockColumnCSVSink

观察 MemoryOptimizationObserver 事件数 + BlockColumnCSVSink 写出能力。""")
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    import tempfile
    from pathlib import Path
    from typing import Dict, List

    from scalim.execution.engine import ScalimEngine
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.memory import MemoryOptimizationObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks import BlockColumnCSVSink, ColumnCSVSink
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output

    return (
        BlockColumnCSVSink,
        ColumnCSVSink,
        Dict,
        InMemoryColumnSink,
        List,
        MemoryOptimizationObserver,
        ObserverManager,
        Path,
        PlanBuilder,
        ScalimEngine,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
        build_test_config_small,
        tempfile,
        verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL)
    print("cfg built, {} targets".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    print("demand.fields={} plan.sources={}".format(len(demand.fields), plan.metadata.total_sources))
    return demand, plan, runtime_bindings


@app.cell
def _(
    BlockColumnCSVSink,
    ColumnCSVSink,
    InMemoryColumnSink,
    MemoryOptimizationObserver,
    ObserverManager,
    ScalimEngine,
    demand,
    plan,
    runtime_bindings,
    targets,
    tempfile,
    verify_scalim_output,
):
    observer_manager = ObserverManager()
    mem_obs = MemoryOptimizationObserver()
    observer_manager.register(mem_obs)

    e1 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, observer_manager=observer_manager, batch_size=10)

    with tempfile.TemporaryDirectory() as tmpdir:
        tp = Path(tmpdir)
        col_csv = tp / "column.csv"
        with ColumnCSVSink(str(col_csv), field_names=targets) as col_sink:
            e1.run(main_rows=None, sink=col_sink)

        # Memory-sink re-run for verification
        e2 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with InMemoryColumnSink(field_names=targets) as mem_sink:
            e2.run(main_rows=None, sink=mem_sink)
            mem_results = mem_sink.get_rows()

        verification = verify_scalim_output(mem_results, fields_to_check=targets)

        # BlockColumnCSVSink demo
        block_csv = tp / "block.csv"
        e3 = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10)
        with BlockColumnCSVSink(str(block_csv), field_names=targets[:10], write_delay=0.0) as block_sink:
            e3.run(main_rows=None, sink=block_sink)

    print(
        "mem_results={} verify={} col_write_events={} field_slim_events={}".format(
            len(mem_results), verification.passed, len(mem_obs.column_write_events), len(mem_obs.field_slim_events)
        )
    )
    return block_sink, mem_obs, mem_results, verification


@app.cell
def _(mem_obs, mem_results, verification):
    passed = bool(verification.passed and len(mem_obs.column_write_events) > 0)
    summary = "rows={} verify={} column_write_events={}".format(len(mem_results), verification.passed, len(mem_obs.column_write_events))
    if not verification.passed:
        summary = summary + "\n" + verification.summary

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {
            "rows": len(mem_results),
            "verification": verification,
            "column_write_events": len(mem_obs.column_write_events),
            "field_slim_events": len(mem_obs.field_slim_events),
        },
    }
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
