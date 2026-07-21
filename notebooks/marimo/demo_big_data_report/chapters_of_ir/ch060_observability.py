"""Cells-native: ch060_observability — Performance, Relation, Trace, RowGap observers."""
import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Observability: Performance, Relation, Trace, RowGap

注册四种 observer 并验证指标收集无误。""")
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
    from typing import Dict, Sequence

    from scalim.execution.engine import ScalimEngine
    from scalim.ob.manager import ObserverManager
    from scalim.ob.presets.execution_trace import ExecutionTraceObserver
    from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
    from scalim.ob.presets.relations import RelationConfig, RelationObserver
    from scalim.ob.presets.row_gap import RowGapObserver
    from scalim.planning import PlanBuilder
    from scalim.sinks.memory import InMemoryColumnSink
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import (
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        build_ecommerce_runtime_bindings,
    )
    from scalim_misc.demo_big_data_report.verification import verify_scalim_output
    return (
        Dict, ExecutionTraceObserver, InMemoryColumnSink, ObserverManager,
        PerformanceConfig, PerformanceObserver, PlanBuilder, RelationConfig,
        RelationObserver, RowGapObserver, ScalimEngine, Sequence,
        TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings,
        build_test_config_small, verify_scalim_output,
    )


@app.cell
def _(build_test_config_small, TARGET_FIELDS_FULL):
    cfg = build_test_config_small()
    targets = list(TARGET_FIELDS_FULL[:12])
    print("cfg + targets({})".format(len(targets)))
    return cfg, targets


@app.cell
def _(PlanBuilder, build_ecommerce_model, build_ecommerce_runtime_bindings, cfg, targets):
    demand = build_ecommerce_model(cfg)
    runtime_bindings = build_ecommerce_runtime_bindings()
    plan = PlanBuilder(demand).build(targets=targets)
    return demand, plan, runtime_bindings


@app.cell
def _(
    ExecutionTraceObserver, InMemoryColumnSink, ObserverManager,
    PerformanceConfig, PerformanceObserver, RelationConfig, RelationObserver,
    RowGapObserver, ScalimEngine,
    demand, plan, runtime_bindings, targets, verify_scalim_output,
):
    perf_obs = PerformanceObserver(config=PerformanceConfig(metrics={"duration", "memory"}, sampling_interval=1, report_format="none"))
    rel_obs = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
    trace_obs = ExecutionTraceObserver()
    gap_obs = RowGapObserver(primary_loader_name="orders", data_loader_names={"customers", "products"}, sample_limit=3)

    observer_manager = ObserverManager()
    for ob in [perf_obs, rel_obs, trace_obs, gap_obs]:
        observer_manager.register(ob)

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings,
                          observer_manager=observer_manager, batch_size=10)
    with InMemoryColumnSink(field_names=targets) as mem_sink:
        engine.run(main_rows=None, sink=mem_sink)
        rows = mem_sink.get_rows()

    verification = verify_scalim_output(rows, fields_to_check=targets)
    metrics = perf_obs.get_metrics()
    rel_metrics = rel_obs.get_metrics()

    print("rows={} verify={}".format(len(rows), verification.passed))
    print("trace_batches={} loader_stats={} rel_lookups={}".format(
        len(trace_obs.batches), len(metrics.loader_stats), rel_metrics.total_lookups))
    print("gap_expected={} actual={} missing={}".format(gap_obs.total_expected, gap_obs.total_actual, gap_obs.total_missing))
    return gap_obs, metrics, rel_metrics, rows, trace_obs, verification


@app.cell
def _(gap_obs, metrics, rel_metrics, rows, trace_obs, verification):
    passed = bool(verification.passed and len(trace_obs.batches) > 0
                  and len(metrics.loader_stats) > 0 and int(rel_metrics.total_lookups) > 0)
    summary = "rows={} verify={} trace_batches={} loader_metrics={} rel_lookups={} gap_expected={}".format(
        len(rows), verification.passed, len(trace_obs.batches), len(metrics.loader_stats),
        int(rel_metrics.total_lookups), gap_obs.total_expected)

    chapter_result = {
        "passed": passed,
        "summary": summary,
        "details": {"rows": len(rows), "trace_batches": len(trace_obs.batches),
                    "loader_metrics_count": len(metrics.loader_stats),
                    "rel_lookups": int(rel_metrics.total_lookups),
                    "rel_hits": int(rel_metrics.hit_count),
                    "rel_misses": int(rel_metrics.miss_count),
                    "gap_expected": gap_obs.total_expected,
                    "gap_actual": gap_obs.total_actual,
                    "gap_missing": gap_obs.total_missing},
    }
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])),
               kind="success" if ok else "danger")
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
