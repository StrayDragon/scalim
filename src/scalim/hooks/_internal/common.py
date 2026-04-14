import logging
from collections.abc import Set as AbstractSet
from typing import Any, Callable, Dict, Optional, Set, Tuple

from ..._internal.loggingx import prefix
from ...events import (
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_BATCH_END,
    EVENT_BATCH_START,
    EVENT_COLUMN_WRITE,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_ERROR,
    EVENT_FIELD_COMPUTE,
    EVENT_FIELD_SLIM,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_LOADER_SLIM,
    EVENT_OPERATOR_SPAN,
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_RELATION_LOOKUP,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
    EVENT_STAGE_SPAN,
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
)

_logger = logging.getLogger(__name__)

HOOK_RAISED_EXCEPTION_WARNING = prefix("hooks") + "钩子 %s.%s 抛出异常"

_HOOK_TYPED_DISPATCH_MAP: Dict[str, str] = {
    EVENT_PIPELINE_START: "on_pipeline_start",
    EVENT_PIPELINE_END: "on_pipeline_end",
    EVENT_BATCH_START: "on_batch_start",
    EVENT_BATCH_END: "on_batch_end",
    EVENT_LOADER_CALL: "on_loader_call",
    EVENT_FIELD_COMPUTE: "on_field_compute",
    EVENT_ERROR: "on_error",
    EVENT_DIAGNOSTIC_WARNING: "on_diagnostic_warning",
    EVENT_FIELD_SLIM: "on_field_slim",
    EVENT_ROW_WRITE: "on_row_write",
    EVENT_ROW_RELEASE: "on_row_release",
    EVENT_LOADER_SLIM: "on_loader_slim",
    EVENT_COLUMN_WRITE: "on_column_write",
}

HOOK_TYPED_DISPATCH_MAP: Dict[str, str] = _HOOK_TYPED_DISPATCH_MAP

CATALOG_EVENT_TYPES: Tuple[str, ...] = (
    EVENT_PIPELINE_START,
    EVENT_PIPELINE_END,
    EVENT_BATCH_START,
    EVENT_BATCH_END,
    EVENT_LOADER_CALL,
    EVENT_LOADER_RETRY,
    EVENT_FIELD_COMPUTE,
    EVENT_ERROR,
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_FIELD_SLIM,
    EVENT_ROW_WRITE,
    EVENT_ROW_RELEASE,
    EVENT_LOADER_SLIM,
    EVENT_COLUMN_WRITE,
    EVENT_RELATION_LOOKUP,
    EVENT_STAGE_SPAN,
    EVENT_OPERATOR_SPAN,
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
    EVENT_WORKFLOW_NODE_START,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_CANCELLED,
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
        validated.add(item)
    return validated


__all__ = ()
