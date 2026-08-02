"""Wrap typed event payloads in Event envelopes for direct handler calls in tests."""

from typing import Any, Dict, Optional, Type

from scalim.events import Event, EventType
from scalim.events._events import (
    AdaptiveSchedulerDecisionEvent,
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    OperatorSpanEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RelationLookupEvent,
    RowReleaseEvent,
    RowWriteEvent,
    StageSpanEvent,
)

_PAYLOAD_EVENT_TYPES = {
    PipelineStartEvent: EventType.PIPELINE_START,
    PipelineEndEvent: EventType.PIPELINE_END,
    BatchStartEvent: EventType.BATCH_START,
    BatchEndEvent: EventType.BATCH_END,
    LoaderCallEvent: EventType.LOADER_CALL,
    FieldComputeEvent: EventType.FIELD_COMPUTE,
    ErrorEvent: EventType.ERROR,
    DiagnosticWarningEvent: EventType.DIAGNOSTIC_WARNING,
    FieldSlimEvent: EventType.FIELD_SLIM,
    RowWriteEvent: EventType.ROW_WRITE,
    RowReleaseEvent: EventType.ROW_RELEASE,
    LoaderSlimEvent: EventType.LOADER_SLIM,
    ColumnWriteEvent: EventType.COLUMN_WRITE,
    RelationLookupEvent: EventType.RELATION_LOOKUP,
    StageSpanEvent: EventType.STAGE_SPAN,
    OperatorSpanEvent: EventType.OPERATOR_SPAN,
    AdaptiveSchedulerDecisionEvent: EventType.ADAPTIVE_SCHEDULER_DECISION,
    OutputTargetEndEvent: EventType.OUTPUT_TARGET_END,
}


def event_envelope(
    payload: Any,
    *,
    run_id: str = "run",
    timestamp: float = 0.0,
    meta: Optional[Dict[str, Any]] = None,
    seq: int = 0,
) -> Event:
    payload_type = type(payload)
    try:
        event_type = _PAYLOAD_EVENT_TYPES[payload_type]
    except KeyError:
        msg = "unsupported payload type for test Event envelope: {}".format(payload_type.__name__)
        raise TypeError(msg) from None
    return Event(
        event_type=event_type,
        timestamp=timestamp,
        run_id=run_id,
        payload=payload,
        meta={} if meta is None else meta,
        seq=seq,
    )
