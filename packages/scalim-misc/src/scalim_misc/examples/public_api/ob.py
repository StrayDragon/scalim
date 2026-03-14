from __future__ import annotations

from scalim.events.catalog import EVENT_PIPELINE_END, EVENT_PIPELINE_START
from scalim.ob import Observability

from .._types import EXAMPLE_KIND_SMOKE, ExampleResult


def run_public_api_observability() -> ExampleResult:
    """覆盖 `scalim.ob.__all__` 的最小示例: 构建 capture manager 并断言事件序."""
    ob = Observability()
    manager = ob.build_manager(mode="capture")
    manager.emit_pipeline_start(targets=["item_id"], batch_size=2)
    manager.emit_pipeline_end(total_batches=1, total_duration=0.01)

    events = manager.drain_events()
    passed = bool([e.event_type for e in events] == [EVENT_PIPELINE_START, EVENT_PIPELINE_END])
    summary = "events={} types={}".format(len(events), ",".join(e.event_type for e in events))
    return ExampleResult(
        example_id="public_api/ob",
        passed=passed,
        kind=EXAMPLE_KIND_SMOKE,
        summary=summary,
        details={"event_types": [e.event_type for e in events]},
    )
