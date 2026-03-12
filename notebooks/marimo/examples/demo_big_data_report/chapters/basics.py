from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink

from notebooks.marimo.examples.demo_big_data_report._loaders import ECommerceConfig, load_orders, set_config
from notebooks.marimo.examples.demo_big_data_report._shared import build_ecommerce_model
from notebooks.marimo.examples.demo_big_data_report._verification import VerificationResult, verify_order_by, verify_scalim_output

from ._types import ChapterResult


def run_basics(
    cfg: ECommerceConfig,
    *,
    targets: Sequence[str],
    batch_size: int = 100,
    row_limit: Optional[int] = None,
) -> ChapterResult:
    """`IR` → `Plan` → `Engine` → `Sink` 的最小主线(含对拍)."""
    set_config(cfg)

    demand = build_ecommerce_model(cfg)
    targets_list = list(targets)
    plan = PlanBuilder(demand).build(targets=targets_list)

    main_rows = list(load_orders())
    if row_limit is not None:
        main_rows = main_rows[: int(row_limit)]

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
    start = time.time()
    with InMemoryColumnSink(field_names=targets_list) as sink:
        engine.run(main_rows=main_rows, sink=sink)
        results = sink.get_rows()
    elapsed = time.time() - start

    verification: VerificationResult = verify_scalim_output(results, fields_to_check=targets_list)
    order_by = verify_order_by(results, ["order_id"])

    passed = bool(verification.passed and order_by.passed)
    summary = "rows={} elapsed={:.3f}s verify={} order_by={}".format(len(results), elapsed, verification.passed, order_by.passed)
    if not passed:
        summary = summary + "\n" + verification.summary + "\n" + order_by.message

    details: Dict[str, Any] = {
        "elapsed_seconds": elapsed,
        "rows": len(results),
        "plan_total_fields": plan.metadata.total_fields,
        "plan_total_sources": plan.metadata.total_sources,
        "verification": verification,
        "order_by": order_by,
    }
    return ChapterResult(chapter_id="basics", passed=passed, summary=summary, details=details)
