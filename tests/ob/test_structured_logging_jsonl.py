import io
import json
import logging

from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    StageSpanEvent,
)
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.relations import RelationConfig, RelationObserver
from scalim.ob.structured_logging import install_jsonl_logging, log_context, normalize_keys_to_full
from tests.support.event_envelope import event_envelope


def test_jsonl_logging_is_line_oriented_and_includes_context() -> None:
    root = logging.getLogger("scalim")
    orig_handlers = list(root.handlers)
    orig_level = int(root.level)
    orig_propagate = bool(root.propagate)

    try:
        # isolate: remove any pre-existing jsonl handler
        root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]

        buf = io.StringIO()
        install_jsonl_logging(stream=buf, profile="compact")

        with log_context(run_id="run_x", demand="demo", workflow_node_id="node_1", demand_path="path/to/demand.yaml"):
            rel_logger = logging.getLogger("scalim.relations")
            rel = RelationObserver(config=RelationConfig(report_format="console", sampling_rate=1.0, logger=rel_logger))
            rel.record_lookup(row_id=1, fk_raw=1, fk_normalized=1, target_source="customers", result="hit")
            rel.print_summary()

            perf_logger = logging.getLogger("scalim.performance")
            perf = PerformanceObserver(
                config=PerformanceConfig(
                    metrics={"duration"},
                    report_format="console",
                    include_loader_top_n=1,
                    include_advisor_hints=True,
                    logger=perf_logger,
                )
            )
            perf.on_pipeline_start(event_envelope(PipelineStartEvent(targets=["x"], batch_size=3)))
            perf.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2, 3])))
            perf.on_stage_span(event_envelope(StageSpanEvent(batch_num=1, stage="stream", duration=0.01)))
            perf.on_stage_span(event_envelope(StageSpanEvent(batch_num=1, stage="loader", duration=0.1)))
            perf.on_stage_span(event_envelope(StageSpanEvent(batch_num=1, stage="compute", duration=0.05)))
            perf.on_stage_span(event_envelope(StageSpanEvent(batch_num=1, stage="write", duration=0.02)))
            perf.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.3)))
            perf.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.3)))

        text = buf.getvalue()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert lines

        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict)
            full = normalize_keys_to_full(obj)
            for k in ("timestamp", "level", "logger", "message"):
                assert k in full
            assert full["context"]["run_id"] == "run_x"
            assert full["context"]["demand"] == "demo"
            assert full["context"]["workflow_node_id"] == "node_1"
            assert full["context"]["demand_path"] == "path/to/demand.yaml"
    finally:
        root.handlers[:] = orig_handlers
        root.setLevel(orig_level)
        root.propagate = orig_propagate
