# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from collections.abc import Set as AbstractSet
from typing import Any, Optional, Set, Tuple, cast

from ...events.catalog import (
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
    EVENT_PIPELINE_END,
    EVENT_PIPELINE_START,
    EVENT_RELATION_LOOKUP,
    EVENT_ROW_RELEASE,
    EVENT_ROW_WRITE,
    EVENT_STAGE_SPAN,
)

OBSERVER_RAISED_EXCEPTION_WARNING = "观察者 %s.%s 抛出异常"
OBSERVER_CLOSE_RAISED_EXCEPTION_WARNING = "观察者 %s 关闭时抛出异常"

_CATALOG_EVENT_TYPES: Tuple[str, ...] = (
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
    EVENT_ADAPTIVE_SCHEDULER_DECISION,
)

_CATALOG_EVENT_TYPES_SET: Set[str] = set(_CATALOG_EVENT_TYPES)
_DEFAULT_MAX_RECORDED_EVENTS = 10_000
_CAPTURE_OVERFLOW_POLICIES = ("raise", "drop-oldest", "drop-newest")


class ObserverCaptureOverflowError(RuntimeError):
    pass


def _validate_event_types(observer: Any, value: Any) -> Optional[Set[str]]:
    if value is None:
        return None
    if not isinstance(value, AbstractSet):
        msg = "observer.event_types must be None or Set[str]; got {} for {}".format(type(value).__name__, type(observer).__name__)
        raise TypeError(msg)
    for item in value:
        if not isinstance(item, str):
            msg = "observer.event_types must contain only str; got {} element {!r} for {}".format(
                type(item).__name__,
                item,
                type(observer).__name__,
            )
            raise TypeError(msg)
    return cast("Set[str]", value)
