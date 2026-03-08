from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, cast

from ...events.event import Event
from ...events.events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from ...vendor.compact.typing_extensionsx import Protocol
from ..dispatch import HookDispatchStrategy

if TYPE_CHECKING:
    import threading


class ExecutionHookLike(Protocol):
    def on_pipeline_start(self, event: PipelineStartEvent) -> None: ...

    def on_pipeline_end(self, event: PipelineEndEvent) -> None: ...

    def on_batch_start(self, event: BatchStartEvent) -> None: ...

    def on_batch_end(self, event: BatchEndEvent) -> None: ...

    def on_loader_call(self, event: LoaderCallEvent) -> None: ...

    def on_field_compute(self, event: FieldComputeEvent) -> None: ...

    def on_error(self, event: ErrorEvent) -> None: ...

    def on_diagnostic_warning(self, event: DiagnosticWarningEvent) -> None: ...

    def on_field_slim(self, event: FieldSlimEvent) -> None: ...

    def on_row_write(self, event: RowWriteEvent) -> None: ...

    def on_row_release(self, event: RowReleaseEvent) -> None: ...

    def on_loader_slim(self, event: LoaderSlimEvent) -> None: ...

    def on_column_write(self, event: ColumnWriteEvent) -> None: ...


HookTypedHandler = Callable[[Any], Any]
HookOnEventHandler = Callable[[Event], Any]
HookTypedHandlerPair = Tuple[ExecutionHookLike, HookTypedHandler]
HookOnEventHandlerPair = Tuple[ExecutionHookLike, HookOnEventHandler]


class HookManagerLike(Protocol):
    hooks: List[ExecutionHookLike]
    has_hooks: bool
    typed_handlers_by_event_type: Dict[str, Tuple[HookTypedHandlerPair, ...]]
    on_event_handlers_by_event_type: Dict[str, Tuple[HookOnEventHandlerPair, ...]]
    debug_mode: bool
    fallback_logger_enabled: bool
    loader_result_policy: str
    loader_result_sample_size: int
    lock: "threading.RLock"
    diagnostic_warning_emitted: bool
    dispatch_strategy: HookDispatchStrategy
    base_hook_on_event: Optional[Callable[..., None]]
    base_hook_typed_handlers: Dict[str, Optional[Callable[..., None]]]


class HookManagerBase(object):
    def _manager(self) -> HookManagerLike:
        return cast("HookManagerLike", cast("object", self))

    def _rebuild_subscription_cache(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def _summarize_result(self, result: Any) -> Dict[str, Any]:  # pragma: no cover
        _ = result
        raise NotImplementedError

    def _sample_result(self, result: Any) -> Any:  # pragma: no cover
        _ = result
        raise NotImplementedError


__all__ = [
    "ExecutionHookLike",
    "HookManagerBase",
    "HookManagerLike",
    "HookOnEventHandler",
    "HookOnEventHandlerPair",
    "HookTypedHandler",
    "HookTypedHandlerPair",
]
