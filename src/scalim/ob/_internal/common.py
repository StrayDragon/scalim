from collections.abc import Set as AbstractSet
from typing import Any, Optional, Set, Tuple

from ..._internal.loggingx import prefix
from ...events import EventType
from ...exceptions import ScalimObserverError
from ...vendor.compact.typing_extensionsx import Literal

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


ObserverManagerModeValue = Literal["process", "capture"]
"""观察者管理器模式的字符串字面量类型(对外配置/状态边界)."""

ObserverManagerModeLike = Optional[ObserverManagerModeValue]

_OBSERVER_MANAGER_MODE_PROCESS: ObserverManagerModeValue = "process"
_OBSERVER_MANAGER_MODE_CAPTURE: ObserverManagerModeValue = "capture"
_OBSERVER_MANAGER_MODES = (_OBSERVER_MANAGER_MODE_PROCESS, _OBSERVER_MANAGER_MODE_CAPTURE)
_OBSERVER_MANAGER_MODES_LABEL = "process/capture"

CaptureOverflowPolicyValue = Literal["raise", "drop-oldest", "drop-newest"]
"""捕获溢出策略的字符串字面量类型(对外配置/状态边界)."""

CaptureOverflowPolicyLike = Optional[CaptureOverflowPolicyValue]

_CAPTURE_OVERFLOW_POLICY_RAISE: CaptureOverflowPolicyValue = "raise"
_CAPTURE_OVERFLOW_POLICY_DROP_OLDEST: CaptureOverflowPolicyValue = "drop-oldest"
_CAPTURE_OVERFLOW_POLICY_DROP_NEWEST: CaptureOverflowPolicyValue = "drop-newest"
CAPTURE_OVERFLOW_POLICIES = (
    _CAPTURE_OVERFLOW_POLICY_RAISE,
    _CAPTURE_OVERFLOW_POLICY_DROP_OLDEST,
    _CAPTURE_OVERFLOW_POLICY_DROP_NEWEST,
)
_CAPTURE_OVERFLOW_POLICIES_LABEL = "raise/drop-oldest/drop-newest"


class ScalimObserverCaptureOverflowError(ScalimObserverError):
    pass


def normalize_observer_manager_mode(value: object) -> ObserverManagerModeValue:
    if value is None:
        return _OBSERVER_MANAGER_MODE_PROCESS

    if not isinstance(value, str):
        msg = "observer_manager.mode must be a str, got '{}'".format(type(value).__name__)
        raise TypeError(msg)
    if type(value) is not str:
        msg = "observer_manager.mode must be a builtin str, got '{}'; expected one of: {}".format(
            type(value).__name__,
            _OBSERVER_MANAGER_MODES_LABEL,
        )
        raise TypeError(msg)

    normalized = value.strip().lower()
    if not normalized:
        msg = "observer_manager.mode must not be empty; expected one of: {}".format(_OBSERVER_MANAGER_MODES_LABEL)
        raise ValueError(msg)

    if normalized == _OBSERVER_MANAGER_MODE_PROCESS:
        return _OBSERVER_MANAGER_MODE_PROCESS
    if normalized == _OBSERVER_MANAGER_MODE_CAPTURE:
        return _OBSERVER_MANAGER_MODE_CAPTURE

    msg = "Unknown observer_manager.mode: {!r}; expected one of: {}".format(value, _OBSERVER_MANAGER_MODES_LABEL)
    raise ValueError(msg)


def normalize_capture_overflow_policy(
    value: object,
) -> CaptureOverflowPolicyValue:
    if value is None:
        return _CAPTURE_OVERFLOW_POLICY_RAISE

    if not isinstance(value, str):
        msg = "capture_overflow_policy must be a str, got '{}'".format(type(value).__name__)
        raise TypeError(msg)
    if type(value) is not str:
        msg = "capture_overflow_policy must be a builtin str, got '{}'; expected one of: {}".format(
            type(value).__name__,
            _CAPTURE_OVERFLOW_POLICIES_LABEL,
        )
        raise TypeError(msg)

    normalized = value.strip().lower().replace("_", "-")
    if not normalized:
        msg = "capture_overflow_policy must not be empty; expected one of: {}".format(_CAPTURE_OVERFLOW_POLICIES_LABEL)
        raise ValueError(msg)

    if normalized == _CAPTURE_OVERFLOW_POLICY_RAISE:
        return _CAPTURE_OVERFLOW_POLICY_RAISE
    if normalized == _CAPTURE_OVERFLOW_POLICY_DROP_OLDEST:
        return _CAPTURE_OVERFLOW_POLICY_DROP_OLDEST
    if normalized == _CAPTURE_OVERFLOW_POLICY_DROP_NEWEST:
        return _CAPTURE_OVERFLOW_POLICY_DROP_NEWEST

    msg = "Unknown capture_overflow_policy: {!r}; expected one of: {}".format(value, _CAPTURE_OVERFLOW_POLICIES_LABEL)
    raise ValueError(msg)


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
