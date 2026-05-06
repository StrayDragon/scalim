import pickle

import pytest

from scalim._internal.utils.loader_result import (
    LoaderResultPolicy,
    normalize_loader_result_policy,
    parse_loader_result_policy,
)
from scalim.hooks import HookManager
from scalim.ob._internal.common import (
    CaptureOverflowPolicy,
    ObserverManagerMode,
    normalize_capture_overflow_policy,
    normalize_observer_manager_mode,
    parse_capture_overflow_policy,
    parse_observer_manager_mode,
)
from scalim.ob.manager import ObserverManager
from scalim.ob.observability import ObservabilityOptions


class _StrSubclass(str):
    pass


def test_parse_loader_result_policy_returns_builtin_str_literals() -> None:
    assert parse_loader_result_policy(None) == "full"
    assert parse_loader_result_policy(" SUMMARY ") == "summary"
    assert type(parse_loader_result_policy("summary")) is str

    with pytest.raises(ValueError, match=r"loader_result_policy must not be empty"):
        parse_loader_result_policy("")

    with pytest.raises(ValueError, match=r"expected one of: full/summary/sample/none"):
        parse_loader_result_policy("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        parse_loader_result_policy(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        parse_loader_result_policy(_StrSubclass("summary"))


def test_parse_observer_manager_mode_converges_and_fail_fast() -> None:
    assert parse_observer_manager_mode(None) == "process"
    assert parse_observer_manager_mode(" CAPTURE ") == "capture"
    assert type(parse_observer_manager_mode("process")) is str

    with pytest.raises(ValueError, match=r"expected one of: process/capture"):
        parse_observer_manager_mode("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        parse_observer_manager_mode(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        parse_observer_manager_mode(_StrSubclass("process"))


def test_parse_capture_overflow_policy_converges_and_fail_fast() -> None:
    assert parse_capture_overflow_policy(None) == "raise"
    assert parse_capture_overflow_policy("DROP_OLDEST") == "drop-oldest"
    assert parse_capture_overflow_policy("drop_oldest") == "drop-oldest"
    assert type(parse_capture_overflow_policy("raise")) is str

    with pytest.raises(ValueError, match=r"capture_overflow_policy must not be empty"):
        parse_capture_overflow_policy("")

    with pytest.raises(ValueError, match=r"expected one of: raise/drop-oldest/drop-newest"):
        parse_capture_overflow_policy("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        parse_capture_overflow_policy(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        parse_capture_overflow_policy(_StrSubclass("raise"))


def test_manager_policy_fields_are_builtin_str_after_pickle_roundtrip() -> None:
    hook_manager = HookManager(loader_result_policy=LoaderResultPolicy.SUMMARY)
    restored_hook = pickle.loads(pickle.dumps(hook_manager))
    assert type(restored_hook.loader_result_policy) is str
    assert restored_hook.loader_result_policy == "summary"

    observer_manager = ObserverManager(
        mode=ObserverManagerMode.CAPTURE,
        capture_overflow_policy=CaptureOverflowPolicy.DROP_OLDEST,
        loader_result_policy=LoaderResultPolicy.SAMPLE,
    )
    restored_observer = pickle.loads(pickle.dumps(observer_manager))
    assert type(restored_observer.mode) is str
    assert restored_observer.mode == "capture"
    assert type(restored_observer.capture_overflow_policy) is str
    assert restored_observer.capture_overflow_policy == "drop-oldest"
    assert type(restored_observer.loader_result_policy) is str
    assert restored_observer.loader_result_policy == "sample"


def test_different_entrypoints_converge_to_same_normalized_policy_values() -> None:
    manager = HookManager(loader_result_policy=LoaderResultPolicy.SUMMARY)
    options = ObservabilityOptions(loader_result_policy=LoaderResultPolicy.SUMMARY)
    assert manager.loader_result_policy == "summary"
    assert options.loader_result_policy == LoaderResultPolicy.SUMMARY

    manager2 = ObserverManager(mode=ObserverManagerMode.CAPTURE)
    assert manager2.mode == "capture"


def test_public_api_rejects_string_literals_for_policy_fields() -> None:
    with pytest.raises(TypeError, match=r"loader_result_policy must be a LoaderResultPolicy"):
        _ = HookManager(loader_result_policy="summary")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"ObservabilityOptions\.loader_result_policy"):
        _ = ObservabilityOptions(loader_result_policy="summary")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"observer_manager\.mode must be a ObserverManagerMode"):
        _ = ObserverManager(mode="capture")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match=r"capture_overflow_policy must be a CaptureOverflowPolicy"):
        _ = ObserverManager(capture_overflow_policy="drop-oldest")  # type: ignore[arg-type]
