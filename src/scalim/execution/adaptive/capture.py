from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...events.catalog import EVENT_LOADER_CALL
from ...events.events import LoaderCallEvent
from ...hooks.base import HookManager, IExecutionHook
from ...vendor.compact.typing_extensionsx import override


@dataclass(frozen=True)
class HookRecordedEvent:
    event_type: str
    payload: Any


class HookCaptureManager(HookManager):
    """用于“捕获 + 提交时回放”的 `HookManager` 适配器.

    该管理器会记录类型化的 `hook` 负载,但不会调用用户 `hook`.
    `hook.on_event(Event)` 会通过 `ObserverManager` 的捕获模式被记录,并在提交时回放.
    """

    hooks: List[IExecutionHook]
    _recorded_events: List[HookRecordedEvent]

    def __init__(self, source: HookManager) -> None:
        super().__init__(
            enable_debugging=source.debug_mode,
            fallback_logger_enabled=source.fallback_logger_enabled,
            loader_result_policy=source.loader_result_policy,
            loader_result_sample_size=source.loader_result_sample_size,
        )
        # 仅复用原始 `hook` 实例用于订阅发现;捕获模式下不进行分发调用.
        self.hooks = list(source.hooks)
        self._rebuild_subscription_cache()
        self._recorded_events = []

    def drain_events(self) -> List[HookRecordedEvent]:
        if not self._recorded_events:
            return []
        events = list(self._recorded_events)
        self._recorded_events.clear()
        return events

    @override
    def emit_typed(self, event_type: str, payload: Any) -> None:
        if not self._has_hooks:
            return
        if event_type not in self._typed_handlers_by_event_type:
            return
        self._recorded_events.append(HookRecordedEvent(event_type=event_type, payload=payload))

    @override
    def trigger_loader_call(
        self,
        loader_name: str,
        params: Dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: Optional[int] = None,
        cache_status: Optional[str] = None,
        cache_scope: Optional[str] = None,
        lookup_key_count: Optional[int] = None,
        field_keys: Optional[List[str]] = None,
    ) -> None:
        if not self._has_hooks:
            return
        if EVENT_LOADER_CALL not in self._typed_handlers_by_event_type:
            return

        payload = result
        if self.loader_result_policy != "full":
            if self.loader_result_policy == "none":
                payload = None
            elif self.loader_result_policy == "summary":
                payload = self._summarize_result(result)
            elif self.loader_result_policy == "sample":
                payload = self._sample_result(result)

        event = LoaderCallEvent(
            loader_name=loader_name,
            params=params,
            result=payload,
            duration=duration,
            batch_num=batch_num,
            cache_status=cache_status,
            cache_scope=cache_scope,
            lookup_key_count=lookup_key_count,
            field_keys=field_keys,
        )
        self._recorded_events.append(HookRecordedEvent(event_type=EVENT_LOADER_CALL, payload=event))


__all__ = ["HookCaptureManager", "HookRecordedEvent"]
