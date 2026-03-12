from __future__ import annotations

from typing import Any, Dict, List, Sequence

from scalim.execution import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.row_gap import RowGapObserver
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink

from notebooks.marimo.examples.demo_big_data_report._loaders import ECommerceConfig, set_config
from notebooks.marimo.examples.demo_big_data_report._shared import TARGET_FIELDS_FULL, build_ecommerce_model
from notebooks.marimo.examples.demo_big_data_report._verification import VerificationResult, verify_scalim_output

from ._types import ChapterResult


def run_observability(cfg: ECommerceConfig, *, targets: Sequence[str], batch_size: int = 50) -> ChapterResult:
    """可观测性预置: `PerformanceObserver`/`ExecutionTraceObserver`/`RowGapObserver`."""

    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    targets_list = list(targets)
    plan = PlanBuilder(demand).build(targets=targets_list)

    observer_manager = ObserverManager()

    perf_observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration", "memory"}, sampling_interval=1, report_format="none"))
    trace_observer = ExecutionTraceObserver()
    row_gap_observer = RowGapObserver(primary_loader_name="orders", data_loader_names={"customers", "products"}, sample_limit=3)

    observer_manager.register(perf_observer)
    observer_manager.register(trace_observer)
    observer_manager.register(row_gap_observer)

    engine = ScalimEngine(demand=demand, plan=plan, observer_manager=observer_manager, batch_size=int(batch_size))
    with InMemoryColumnSink(field_names=targets_list) as sink:
        engine.run(main_rows=None, sink=sink)
        rows = sink.get_rows()

    verification: VerificationResult = verify_scalim_output(rows, fields_to_check=targets_list)
    metrics = perf_observer.get_metrics()

    passed = bool(verification.passed and len(trace_observer.batches) > 0 and len(metrics.loader_stats) > 0)
    summary = "rows={} verify={} trace_batches={} loader_metrics={} row_gap_expected={}".format(
        len(rows),
        verification.passed,
        len(trace_observer.batches),
        len(metrics.loader_stats),
        row_gap_observer._total_expected,
    )
    if not verification.passed:
        summary = summary + "\n" + verification.summary

    details: Dict[str, Any] = {
        "rows": len(rows),
        "verification": verification,
        "trace_batches": len(trace_observer.batches),
        "loader_metrics_count": len(metrics.loader_stats),
        "row_gap_total_expected": row_gap_observer._total_expected,
        "row_gap_total_actual": row_gap_observer._total_actual,
        "row_gap_total_missing": row_gap_observer._total_missing,
    }
    return ChapterResult(chapter_id="observability", passed=passed, summary=summary, details=details)
