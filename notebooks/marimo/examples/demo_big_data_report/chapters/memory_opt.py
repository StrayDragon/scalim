from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Sequence

from scalim.execution import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.planning import PlanBuilder
from scalim.sinks.sink_csv import BlockColumnCSVSink, ColumnCSVSink
from scalim.sinks.sink_memory import InMemoryColumnSink

from notebooks.marimo.examples.demo_big_data_report._loaders import ECommerceConfig, set_config
from notebooks.marimo.examples.demo_big_data_report._shared import TARGET_FIELDS_FULL, build_ecommerce_model
from notebooks.marimo.examples.demo_big_data_report._verification import VerificationResult, verify_scalim_output

from ._types import ChapterResult


def run_memory_optimization(cfg: ECommerceConfig, *, batch_size: int = 50, write_delay: float = 0.0) -> ChapterResult:
    """字段瘦身/列式写入相关链路(默认关闭演示用延迟)."""
    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    targets: List[str] = list(TARGET_FIELDS_FULL)
    plan = PlanBuilder(demand).build(targets=targets)

    observer_manager = ObserverManager()
    memory_observer = MemoryOptimizationObserver()
    observer_manager.register(memory_observer)

    engine = ScalimEngine(demand=demand, plan=plan, observer_manager=observer_manager, batch_size=int(batch_size))

    with tempfile.TemporaryDirectory() as tmpdir:
        col_csv = os.path.join(tmpdir, "column.csv")
        with ColumnCSVSink(col_csv, field_names=targets) as sink:
            engine.run(main_rows=None, sink=sink)

        # 用内存 `sink` 再跑一遍做对拍(避免解析 `CSV` 的类型损失)
        engine2 = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
        with InMemoryColumnSink(field_names=targets) as mem_sink:
            engine2.run(main_rows=None, sink=mem_sink)
            results = mem_sink.get_rows()

        verification: VerificationResult = verify_scalim_output(results, fields_to_check=targets)

        # `BlockColumnCSVSink`: 仅用于演示,这里强制 `write_delay=0`,避免集成对拍变慢
        block_csv = os.path.join(tmpdir, "block.csv")
        engine3 = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
        with BlockColumnCSVSink(block_csv, field_names=targets[:10], write_delay=float(write_delay)) as block_sink:
            engine3.run(main_rows=None, sink=block_sink)

    passed = bool(verification.passed and len(memory_observer.column_write_events) > 0)
    summary = "rows={} verify={} column_write_events={}".format(len(results), verification.passed, len(memory_observer.column_write_events))
    if not verification.passed:
        summary = summary + "\n" + verification.summary

    details: Dict[str, Any] = {
        "rows": len(results),
        "verification": verification,
        "column_write_events": len(memory_observer.column_write_events),
        "field_slim_events": len(memory_observer.field_slim_events),
    }
    return ChapterResult(chapter_id="memory_opt", passed=passed, summary=summary, details=details)
