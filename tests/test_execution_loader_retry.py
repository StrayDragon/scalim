from typing import List, Optional, Set

import pytest

from scalim.events.catalog import EVENT_ERROR, EVENT_LOADER_RETRY
from scalim.events.event import Event
from scalim.execution.loader_retry import LoaderRetryPolicies, LoaderRetryPolicy
from scalim.execution.run_ir import ExecutionRequest, ExportLayout, OutputSpec, run_ir
from scalim.ob.observer import Observer
from scalim.sinks.sink_memory import InMemoryListSink
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import MainSourceIr


class _CaptureObserver(Observer):
    def __init__(self) -> None:
        self.event_types: Optional[Set[str]] = {EVENT_LOADER_RETRY, EVENT_ERROR}
        self.events: List[Event] = []

    def on_event(self, event: Event) -> None:
        self.events.append(event)


class _TransientError(RuntimeError):
    pass


def test_run_ir_retries_main_source_and_emits_loader_retry_event() -> None:
    calls = {"n": 0}

    def _loader() -> List[dict]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _TransientError("flaky")
        return [{"order_id": 1}]

    def _should_retry(exc: Exception, _ctx) -> bool:  # type: ignore[no-untyped-def]
        return isinstance(exc, _TransientError)

    main_source = MainSourceIr(source_id="orders", loader=_loader)
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)],
        main_source=main_source,
    )

    observer = _CaptureObserver()
    sink = InMemoryListSink()
    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_should_retry,
        max_attempts=3,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
        components=[observer],
        loader_retry=LoaderRetryPolicies(default=policy),
    )

    result = run_ir(demand_ir, request)

    assert result.total_rows == 1
    assert sink.get_data() == [{"order_id": 1}]
    assert calls["n"] == 2

    retry_events = [e for e in observer.events if e.event_type == EVENT_LOADER_RETRY]
    error_events = [e for e in observer.events if e.event_type == EVENT_ERROR]
    assert len(retry_events) == 1
    assert error_events == []
    assert retry_events[0].payload.callsite == "main_source"
    assert retry_events[0].payload.attempt_num == 1


def test_run_ir_retry_give_up_emits_single_error_event() -> None:
    calls = {"n": 0}

    def _loader() -> List[dict]:
        calls["n"] += 1
        raise _TransientError("flaky")

    def _should_retry(exc: Exception, _ctx) -> bool:  # type: ignore[no-untyped-def]
        return isinstance(exc, _TransientError)

    main_source = MainSourceIr(source_id="orders", loader=_loader)
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)],
        main_source=main_source,
    )

    observer = _CaptureObserver()
    sink = InMemoryListSink()
    policy = LoaderRetryPolicy(
        enabled=True,
        should_retry=_should_retry,
        max_attempts=2,
        max_elapsed_seconds=10.0,
        backoff="fixed",
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        jitter=False,
    )
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
        components=[observer],
        loader_retry=LoaderRetryPolicies(default=policy),
    )

    with pytest.raises(_TransientError, match="flaky"):
        _ = run_ir(demand_ir, request)

    assert calls["n"] == 2
    retry_events = [e for e in observer.events if e.event_type == EVENT_LOADER_RETRY]
    error_events = [e for e in observer.events if e.event_type == EVENT_ERROR]

    assert len(retry_events) == 1
    assert len(error_events) == 1
    assert error_events[0].payload.context["attempt_num"] == 2
    assert error_events[0].payload.context["retry_reason"] == "max_attempts_exceeded"
