from __future__ import annotations

from scalim.events.catalog import EVENT_LOADER_CALL, EVENT_PIPELINE_START
from scalim.hooks.base import BaseHook, HookManager


def test_hook_manager_typed_subscription_respects_event_types_filter() -> None:
    class _Hook(BaseHook):
        event_types = {EVENT_LOADER_CALL}

        def on_loader_call(self, event) -> None:  # type: ignore[override]
            _ = event

    manager = HookManager()
    manager.register(_Hook())

    assert manager.wants_typed(EVENT_LOADER_CALL) is True


def test_hook_manager_on_event_subscribes_to_all_catalog_events_when_unfiltered() -> None:
    class _Hook(BaseHook):
        def on_event(self, event) -> None:  # type: ignore[override]
            _ = event

    manager = HookManager()
    manager.register(_Hook())

    assert manager.wants_on_event(EVENT_PIPELINE_START) is True
