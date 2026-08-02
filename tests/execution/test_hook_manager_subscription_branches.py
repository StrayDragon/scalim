from collections.abc import Iterator, Set as AbstractSet

import pytest

from scalim.events import EventType
from scalim.hooks import BaseHook, HookManager


class _OrderedEventTypes(AbstractSet[str]):
    def __init__(self, items: list[str]) -> None:
        self._items = list(items)

    def __contains__(self, item: object) -> bool:
        return item in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)


class _CaptureOnEventHook(BaseHook):
    def __init__(self) -> None:
        self.seen_event_types: list[str] = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.seen_event_types.append(event.event_type)


class _CaptureLoaderCallHook(BaseHook):
    def __init__(self) -> None:
        self.seen_results: list[object] = []

    def on_loader_call(self, event) -> None:  # type: ignore[override]
        self.seen_results.append(event.payload.result)


def test_hook_manager_rejects_bare_str_on_event_types() -> None:
    manager = HookManager()
    hook = _CaptureOnEventHook()
    hook.event_types = _OrderedEventTypes(["unknown", EventType.PIPELINE_START])
    with pytest.raises(TypeError, match=r"contain only EventType"):
        manager.register(hook)


def test_hook_manager_rejects_policy_signal_event_type_for_on_event_catalog() -> None:
    manager = HookManager()
    hook = _CaptureOnEventHook()
    hook.event_types = {EventType.WORKFLOW_STARTED}
    with pytest.raises(ValueError, match=r"unknown event type"):
        manager.register(hook)


def test_hook_manager_loader_call_policy_rejects_unknown() -> None:
    manager = HookManager()
    hook = _CaptureLoaderCallHook()
    manager.register(hook)

    manager.loader_result_policy = "unknown"
    with pytest.raises(ValueError, match=r"Unknown loader_result_policy"):
        manager.trigger_loader_call(loader_name="x", params={}, result={"a": 1}, duration=0.0)


def test_hook_manager_loader_call_policy_normalizes_case_and_updates_manager_state() -> None:
    manager = HookManager()
    hook = _CaptureLoaderCallHook()
    manager.register(hook)

    manager.loader_result_policy = "SUMMARY"
    manager.trigger_loader_call(loader_name="x", params={}, result={"a": 1}, duration=0.0)

    assert manager.loader_result_policy == "summary"
    assert hook.seen_results == [{"type": "dict", "size": 1}]


def test_hook_manager_on_event_subscriptions_ignore_typed_only_event_types() -> None:
    class _CaptureOnEvent(BaseHook):
        def __init__(self) -> None:
            self.seen: list[str] = []

        def on_event(self, event) -> None:  # type: ignore[override]
            self.seen.append(event.event_type)

    manager = HookManager()
    hook = _CaptureOnEvent()
    hook.event_types = {EventType.PRE_USE_BATCH_SIZE}
    manager.register(hook)

    assert manager.wants_on_event(EventType.PRE_USE_BATCH_SIZE) is False
