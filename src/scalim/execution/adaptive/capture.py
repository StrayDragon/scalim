from dataclasses import dataclass
from typing import Any

from ...events.catalog import EVENT_LOADER_CALL
from ...events.events import LoaderCallEvent
from ...hooks.base import HookManager, IExecutionHook
from ...vendor.compact.typing_extensionsx import override


@dataclass(frozen=True)
class HookRecordedEvent:
    event_type: str
    payload: Any


class HookCaptureManager(HookManager):
    """`HookManager` 的捕获适配器：用于捕获并在提交阶段回放。

    该管理器会记录类型化钩子的载荷,但不会调用用户钩子。
    `hook.on_event(Event)` 由 `ObserverManager` 的捕获模式负责捕获,并在提交阶段回放。
    """

    hooks: list[IExecutionHook]
    _recorded_events: list[HookRecordedEvent]

    def __init__(self, source: HookManager) -> None:
        super().__init__(
            enable_debugging=source.debug_mode,
            fallback_logger_enabled=source.fallback_logger_enabled,
            loader_result_policy=source.loader_result_policy,
            loader_result_sample_size=source.loader_result_sample_size,
        )
        # 仅复用原始钩子实例用于订阅发现；在捕获模式下不进行分发。
        self.hooks = list(source.hooks)
        self._rebuild_subscription_cache()
        self._recorded_events = []

    def drain_events(self) -> list[HookRecordedEvent]:
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
        params: dict[str, Any],
        result: Any,
        duration: float,
        *,
        batch_num: int | None = None,
        cache_status: str | None = None,
        cache_scope: str | None = None,
        lookup_key_count: int | None = None,
        field_keys: list[str] | None = None,
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
