from collections.abc import Set as AbstractSet
from typing import Any, Optional, Set, Tuple

from ..._internal.loggingx import prefix
from ..._internal.utils.policy import (
    ensure_policy_enum,
    normalize_token_lower_strip,
    normalize_token_lower_strip_replace,
    parse_policy_value,
)
from ...events import EventType
from ...exceptions import ScalimObserverError
from ...vendor.compact import StrEnum

OBSERVER_RAISED_EXCEPTION_WARNING = prefix("ob") + "观察者 %s.%s 抛出异常"
OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING = prefix("ob") + "观察者 %s 关闭时抛出异常"

CATALOG_EVENT_TYPES: Tuple[str, ...] = (
    EventType.PIPELINE_START,
    EventType.PIPELINE_END,
    EventType.BATCH_START,
    EventType.BATCH_END,
    EventType.LOADER_CALL,
    EventType.LOADER_RETRY,
    EventType.FIELD_COMPUTE,
    EventType.ERROR,
    EventType.DIAGNOSTIC_WARNING,
    EventType.FIELD_SLIM,
    EventType.ROW_WRITE,
    EventType.ROW_RELEASE,
    EventType.LOADER_SLIM,
    EventType.COLUMN_WRITE,
    EventType.RELATION_LOOKUP,
    EventType.STAGE_SPAN,
    EventType.OPERATOR_SPAN,
    EventType.ADAPTIVE_SCHEDULER_DECISION,
    EventType.OUTPUT_TARGET_END,
    EventType.WORKFLOW_NODE_START,
    EventType.WORKFLOW_NODE_END,
    EventType.WORKFLOW_NODE_CANCELLED,
    EventType.WORKFLOW_CACHE_ACQUIRE,
    EventType.WORKFLOW_CACHE_RELEASE,
    EventType.WORKFLOW_CACHE_EVICT,
    EventType.WORKFLOW_RESOURCE_CREATE,
    EventType.WORKFLOW_RESOURCE_WRITE,
    EventType.WORKFLOW_RESOURCE_COMMIT,
    EventType.WORKFLOW_RESOURCE_DISCARD,
)

CATALOG_EVENT_TYPES_SET: Set[str] = set(CATALOG_EVENT_TYPES)
DEFAULT_MAX_RECORDED_EVENTS = 10_000


class ObserverManagerMode(StrEnum):
    PROCESS = "process"
    CAPTURE = "capture"


ObserverManagerModeValue = str
ObserverManagerModeLike = Optional[ObserverManagerModeValue]

_DEFAULT_OBSERVER_MANAGER_MODE = ObserverManagerMode.PROCESS


class CaptureOverflowPolicy(StrEnum):
    RAISE = "raise"
    DROP_OLDEST = "drop-oldest"
    DROP_NEWEST = "drop-newest"


CaptureOverflowPolicyValue = str
CaptureOverflowPolicyLike = Optional[CaptureOverflowPolicyValue]

_DEFAULT_CAPTURE_OVERFLOW_POLICY = CaptureOverflowPolicy.RAISE


class ScalimObserverCaptureOverflowError(ScalimObserverError):
    pass


def format_observer_manager_mode(value: ObserverManagerMode) -> ObserverManagerModeValue:
    return str(value.value)


def parse_observer_manager_mode(value: object) -> ObserverManagerModeValue:
    return parse_policy_value(
        ObserverManagerMode,
        value,
        label="observer_manager.mode",
        default=_DEFAULT_OBSERVER_MANAGER_MODE,
        normalize=normalize_token_lower_strip,
        allow_empty=False,
    )


def normalize_observer_manager_mode(value: ObserverManagerMode) -> ObserverManagerModeValue:
    enum_value = ensure_policy_enum(ObserverManagerMode, value, label="observer_manager.mode")
    return format_observer_manager_mode(enum_value)


def normalize_capture_overflow_policy(
    value: CaptureOverflowPolicy,
) -> CaptureOverflowPolicyValue:
    enum_value = ensure_policy_enum(CaptureOverflowPolicy, value, label="capture_overflow_policy")
    return str(enum_value.value)


def parse_capture_overflow_policy(value: object) -> CaptureOverflowPolicyValue:
    return parse_policy_value(
        CaptureOverflowPolicy,
        value,
        label="capture_overflow_policy",
        default=_DEFAULT_CAPTURE_OVERFLOW_POLICY,
        normalize=lambda v: normalize_token_lower_strip_replace(v, old="_", new="-"),
        allow_empty=False,
    )


def validate_event_types(observer: Any, value: Any) -> Optional[Set[str]]:
    if value is None:
        return None
    if not isinstance(value, AbstractSet):
        msg = "observer.event_types must be None or Set[str]; got {} for {}".format(type(value).__name__, type(observer).__name__)
        raise TypeError(msg)
    normalized: Set[str] = set()
    for item in value:
        if not isinstance(item, str):
            msg = "observer.event_types must contain only str; got {} element {!r} for {}".format(
                type(item).__name__,
                item,
                type(observer).__name__,
            )
            raise TypeError(msg)
        if item not in CATALOG_EVENT_TYPES_SET:
            msg = "observer.event_types contains unknown event type {!r} for {}".format(item, type(observer).__name__)
            raise ValueError(msg)
        normalized.add(item)
    return normalized


__all__ = ()
