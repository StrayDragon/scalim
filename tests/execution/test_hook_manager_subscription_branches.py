from collections.abc import Iterator, Set as AbstractSet

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
        self.seen_results.append(event.result)


def test_hook_manager_ignores_unknown_on_event_types() -> None:
    manager = HookManager()
    hook = _CaptureOnEventHook()
    hook.event_types = _OrderedEventTypes(["unknown", EventType.PIPELINE_START])
    manager.register(hook)

    assert manager.wants_on_event("unknown") is False
    assert manager.wants_on_event(EventType.PIPELINE_START) is True


def test_hook_manager_loader_call_policy_falls_back_when_unknown() -> None:
    manager = HookManager()
    hook = _CaptureLoaderCallHook()
    manager.register(hook)

    manager.loader_result_policy = "unknown"
    manager.trigger_loader_call(loader_name="x", params={}, result={"a": 1}, duration=0.0)
    assert hook.seen_results == [{"a": 1}]
