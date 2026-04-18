import marimo

from typing import Any, Dict, Optional, Sequence

from scalim.execution.engine import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.relations import RelationConfig, RelationObserver
from scalim.ob.presets.row_gap import RowGapObserver
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryColumnSink
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, get_config, set_config
from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL, build_ecommerce_model, build_ecommerce_runtime_bindings
from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")


def run_observability(
    cfg: Optional[ECommerceConfig] = None,
    *,
    targets: Optional[Sequence[str]] = None,
    batch_size: int = 10,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    prev = get_config()
    set_config(cfg)
    try:
        demand = build_ecommerce_model(cfg)
        runtime_bindings = build_ecommerce_runtime_bindings()
        targets_list = list(targets or TARGET_FIELDS_FULL[:12])
        plan = PlanBuilder(demand).build(targets=targets_list)

        observer_manager = ObserverManager()

        perf_observer = PerformanceObserver(
            config=PerformanceConfig(metrics={"duration", "memory"}, sampling_interval=1, report_format="none")
        )
        relation_observer = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
        trace_observer = ExecutionTraceObserver()
        row_gap_observer = RowGapObserver(primary_loader_name="orders", data_loader_names={"customers", "products"}, sample_limit=3)

        observer_manager.register(perf_observer)
        observer_manager.register(relation_observer)
        observer_manager.register(trace_observer)
        observer_manager.register(row_gap_observer)

        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=runtime_bindings,
            observer_manager=observer_manager,
            batch_size=int(batch_size),
        )
        with InMemoryColumnSink(field_names=targets_list) as sink:
            engine.run(main_rows=None, sink=sink)
            rows = sink.get_rows()

        verification: VerificationResult = verify_scalim_output(rows, fields_to_check=targets_list)
        metrics = perf_observer.get_metrics()
        relation_metrics = relation_observer.get_metrics()

        passed = bool(
            verification.passed
            and len(trace_observer.batches) > 0
            and len(metrics.loader_stats) > 0
            and int(relation_metrics.total_lookups) > 0
        )
        summary = "rows={} verify={} trace_batches={} loader_metrics={} relation_lookups={} row_gap_expected={}".format(
            len(rows),
            verification.passed,
            len(trace_observer.batches),
            len(metrics.loader_stats),
            int(relation_metrics.total_lookups),
            row_gap_observer.total_expected,
        )
        if not verification.passed:
            summary = summary + "\n" + verification.summary

        details: Dict[str, Any] = {
            "rows": len(rows),
            "verification": verification,
            "trace_batches": len(trace_observer.batches),
            "loader_metrics_count": len(metrics.loader_stats),
            "relation_total_lookups": int(relation_metrics.total_lookups),
            "relation_hit_count": int(relation_metrics.hit_count),
            "relation_miss_count": int(relation_metrics.miss_count),
            "row_gap_total_expected": row_gap_observer.total_expected,
            "row_gap_total_actual": row_gap_observer.total_actual,
            "row_gap_total_missing": row_gap_observer.total_missing,
        }
        return ExampleResult(
            example_id="demo_big_data_report/ch060_observability",
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_observability()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch060_observability

        本章目标:
        - 演示 observability 相关路径的最小回归入口

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch060_observability.py::run_observability`

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
    from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL

    cfg = build_test_config_small()
    targets = TARGET_FIELDS_FULL[:12]
    result = run_observability(cfg, targets=targets, batch_size=10)
    return TARGET_FIELDS_FULL, cfg, result, targets


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
