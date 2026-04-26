from collections.abc import Set as AbstractSet
from typing import Any, Callable, Dict, Optional, Set, Tuple

from ..._internal.loggingx import prefix
from ...events import EventType

HOOK_RAISED_EXCEPTION_WARNING = prefix("hooks") + "钩子 %s.%s 抛出异常"

_HOOK_TYPED_DISPATCH_MAP: Dict[str, str] = {
    EventType.PIPELINE_START: "on_pipeline_start",
    EventType.PIPELINE_END: "on_pipeline_end",
    EventType.BATCH_START: "on_batch_start",
    EventType.BATCH_END: "on_batch_end",
    EventType.LOADER_CALL: "on_loader_call",
    EventType.FIELD_COMPUTE: "on_field_compute",
    EventType.ERROR: "on_error",
    EventType.DIAGNOSTIC_WARNING: "on_diagnostic_warning",
    EventType.FIELD_SLIM: "on_field_slim",
    EventType.ROW_WRITE: "on_row_write",
    EventType.ROW_RELEASE: "on_row_release",
    EventType.LOADER_SLIM: "on_loader_slim",
    EventType.COLUMN_WRITE: "on_column_write",
    EventType.PRE_USE_BATCH_SIZE: "on_pre_use_batch_size",
}

HOOK_TYPED_DISPATCH_MAP: Dict[str, str] = _HOOK_TYPED_DISPATCH_MAP

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
    EventType.WORKFLOW_NODE_START,
    EventType.WORKFLOW_NODE_END,
    EventType.WORKFLOW_NODE_CANCELLED,
)


def resolve_mro_attr(cls: type, name: str) -> Any:
    for mro_cls in cls.__mro__:
        cls_dict = mro_cls.__dict__
        if name in cls_dict:
            return cls_dict[name]
    return None


def read_optional_attr(obj: Any, name: str) -> Any:
    try:
        return obj.__getattribute__(name)
    except AttributeError:
        return None


def read_callable_attr(obj: Any, name: str) -> Optional[Callable[..., Any]]:
    value = read_optional_attr(obj, name)
    if value is None or not callable(value):
        return None
    return value


_CATALOG_EVENT_TYPES_SET: Set[str] = set(CATALOG_EVENT_TYPES) | set(_HOOK_TYPED_DISPATCH_MAP.keys())


def validate_event_types(hook: Any, value: Any) -> Optional[Set[str]]:
    if value is None:
        return None
    if not isinstance(value, AbstractSet):
        msg = "hook.event_types must be None or Set[str]; got {} for {}".format(type(value).__name__, type(hook).__name__)
        raise TypeError(msg)
    validated: Set[str] = set()
    for item in value:
        if not isinstance(item, str):
            msg = "hook.event_types must contain only str; got {} element {!r} for {}".format(
                type(item).__name__, item, type(hook).__name__
            )
            raise TypeError(msg)
        if item not in _CATALOG_EVENT_TYPES_SET:
            msg = "hook.event_types contains unknown event type {!r} for {}".format(item, type(hook).__name__)
            raise ValueError(msg)
        validated.add(item)
    return validated


__all__ = ()
