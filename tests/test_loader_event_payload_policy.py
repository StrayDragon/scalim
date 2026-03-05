from collections.abc import Sequence

import pytest

from scalim.events.events import LoaderCallEvent
from scalim.ob.observer import EventDispatchObserver
from scalim.ob.manager import ObserverManager


class _CaptureObserver(EventDispatchObserver):
    def __init__(self) -> None:
        self.events = []  # type: ignore[var-annotated]

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        self.events.append(event)


class _BadSequence(Sequence):
    def __len__(self) -> int:
        return 2

    def __getitem__(self, index):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


def _emit_event(policy: str, sample_size: int, result) -> object:  # type: ignore[no-untyped-def]
    observer = _CaptureObserver()
    manager = ObserverManager(
        observers=[observer],
        loader_result_policy=policy,
        loader_result_sample_size=sample_size,
    )
    manager.emit_loader_call("demo", {"p": 1}, result, 0.1)
    return observer.events[0]


def test_loader_event_payload_full() -> None:
    result = [1, 2, 3]
    event = _emit_event("full", 2, result)

    assert event.result is result


def test_loader_event_payload_summary() -> None:
    result = [1, 2, 3, 4]
    event = _emit_event("summary", 2, result)

    assert event.result["type"] == "list"
    assert event.result["size"] == 4


def test_loader_event_payload_sample() -> None:
    result = [1, 2, 3]
    event = _emit_event("sample", 2, result)

    assert event.result == [1, 2]


def test_loader_event_payload_none() -> None:
    result = [1]
    event = _emit_event("none", 2, result)

    assert event.result is None


def test_loader_event_payload_invalid_policy_raises() -> None:
    with pytest.raises(ValueError, match="Unknown loader_result_policy"):
        ObserverManager(loader_result_policy="bad")


def test_loader_event_payload_sample_mapping() -> None:
    result = {"a": 1, "b": 2}
    event = _emit_event("sample", 1, result)

    assert isinstance(event.result, dict)
    assert len(event.result) == 1
    assert set(event.result).issubset({"a", "b"})


def test_loader_event_payload_sample_tuple() -> None:
    result = (1, 2, 3)
    event = _emit_event("sample", 2, result)

    assert event.result == [1, 2]


def test_loader_event_payload_sample_set() -> None:
    result = {1, 2, 3}
    event = _emit_event("sample", 2, result)

    assert len(event.result) == 2
    assert set(event.result).issubset({1, 2, 3})


def test_loader_event_payload_sample_string() -> None:
    result = "abcdef"
    event = _emit_event("sample", 3, result)

    assert event.result == "abc"


def test_loader_event_payload_sample_sequence_fallbacks() -> None:
    result = _BadSequence()
    event = _emit_event("sample", 2, result)

    assert event.result["type"] == "_BadSequence"
    assert event.result["size"] == 2
