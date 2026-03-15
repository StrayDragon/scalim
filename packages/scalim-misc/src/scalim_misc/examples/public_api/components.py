from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from scalim.events.catalog import EVENT_LOADER_CALL, EVENT_PIPELINE_END, EVENT_PIPELINE_START
from scalim.events.event import Event
from scalim.execution.run_ir import ExecutionRequest, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.hooks.base import BaseHook
from scalim.ob.observer import Observer
from scalim.sinks.sink_memory import InMemoryRowSink

from .._types import EXAMPLE_KIND_ORACLE, ExampleResult
from ._fixtures import build_minimal_public_api_ir


@dataclass
class _HookStats:
    pipeline_start: int = 0
    pipeline_end: int = 0
    loader_calls: List[str] = field(default_factory=list)


class _CounterHook(BaseHook):
    event_types: Optional[Set[str]] = {EVENT_PIPELINE_START, EVENT_PIPELINE_END, EVENT_LOADER_CALL}

    def __init__(self) -> None:
        self.stats = _HookStats()

    def on_pipeline_start(self, event: Any) -> None:  # noqa: ANN401
        self.stats.pipeline_start += 1

    def on_pipeline_end(self, event: Any) -> None:  # noqa: ANN401
        self.stats.pipeline_end += 1

    def on_loader_call(self, event: Any) -> None:  # noqa: ANN401
        loader_name = getattr(event, "loader_name", None)
        if loader_name:
            self.stats.loader_calls.append(str(loader_name))


class _TraceObserver(Observer):
    event_types: Optional[Set[str]] = {EVENT_PIPELINE_START, EVENT_PIPELINE_END, EVENT_LOADER_CALL}

    def __init__(self) -> None:
        self.seen_event_types: List[str] = []

    def on_event(self, event: Event) -> None:
        self.seen_event_types.append(str(event.event_type))


def run_public_api_components() -> ExampleResult:
    """覆盖 `components=[Observer(), IExecutionHook()]` 的最小示例: 自定义 hook/observer 并断言其生效."""
    demand_ir = build_minimal_public_api_ir()
    export_layout = export_layout_from_demand_ir(
        demand_ir,
        ("item_id", "dim_id", "value_plus_one"),
        header_fields_output_by="field_id",
    )

    sink = InMemoryRowSink()
    hook = _CounterHook()
    observer = _TraceObserver()

    request = ExecutionRequest(
        export_layout=export_layout,
        output=OutputSpec(path=None),
        sink=sink,
        output_composition=None,
        observability=None,
        guardrails=None,
        loader_retry=None,
        components=[observer, hook],
        batch_size=10,
        parallel_mode="seq",
        max_workers=0,
    )
    core = run_ir(demand_ir, request)
    rows = sink.get_data()

    expected_rows = 3
    expected_first_value = 2
    passed = bool(
        core.total_rows == len(rows) == expected_rows
        and rows[0].get("value_plus_one") == expected_first_value
        and hook.stats.pipeline_start == 1
        and hook.stats.pipeline_end == 1
        and hook.stats.loader_calls == ["items"]
        and observer.seen_event_types.count(EVENT_PIPELINE_START) == 1
        and observer.seen_event_types.count(EVENT_PIPELINE_END) == 1
        and observer.seen_event_types.count(EVENT_LOADER_CALL) == 1
    )
    summary = "rows={} hooks(pipeline_start={}, pipeline_end={}, loader_calls={}) observer_events={}".format(
        len(rows),
        hook.stats.pipeline_start,
        hook.stats.pipeline_end,
        len(hook.stats.loader_calls),
        len(observer.seen_event_types),
    )
    details: Dict[str, Any] = {
        "rows": rows,
        "hook": {
            "pipeline_start": hook.stats.pipeline_start,
            "pipeline_end": hook.stats.pipeline_end,
            "loader_calls": list(hook.stats.loader_calls),
        },
        "observer": {"event_types": list(observer.seen_event_types)},
    }
    return ExampleResult(
        example_id="public_api/components",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )
