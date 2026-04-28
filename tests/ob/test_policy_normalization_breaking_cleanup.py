import pickle

import pytest

from scalim._internal.utils.loader_result import normalize_loader_result_policy
from scalim.hooks import HookManager
from scalim.ob._internal.common import normalize_capture_overflow_policy, normalize_observer_manager_mode
from scalim.ob.manager import ObserverManager
from scalim.ob.observability import ObservabilityOptions


class _StrSubclass(str):
    pass


def test_normalize_loader_result_policy_returns_builtin_str_literals() -> None:
    assert normalize_loader_result_policy(None) == "full"
    assert normalize_loader_result_policy(" SUMMARY ") == "summary"
    assert type(normalize_loader_result_policy("summary")) is str

    with pytest.raises(ValueError, match=r"loader_result_policy must not be empty"):
        normalize_loader_result_policy("")

    with pytest.raises(ValueError, match=r"expected one of: full/summary/sample/none"):
        normalize_loader_result_policy("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        normalize_loader_result_policy(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        normalize_loader_result_policy(_StrSubclass("summary"))


def test_normalize_observer_manager_mode_converges_and_fail_fast() -> None:
    assert normalize_observer_manager_mode(None) == "process"
    assert normalize_observer_manager_mode(" CAPTURE ") == "capture"
    assert type(normalize_observer_manager_mode("process")) is str

    with pytest.raises(ValueError, match=r"expected one of: process/capture"):
        normalize_observer_manager_mode("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        normalize_observer_manager_mode(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        normalize_observer_manager_mode(_StrSubclass("process"))


def test_normalize_capture_overflow_policy_converges_and_fail_fast() -> None:
    assert normalize_capture_overflow_policy(None) == "raise"
    assert normalize_capture_overflow_policy("DROP_OLDEST") == "drop-oldest"
    assert normalize_capture_overflow_policy("drop_oldest") == "drop-oldest"
    assert type(normalize_capture_overflow_policy("raise")) is str

    with pytest.raises(ValueError, match=r"capture_overflow_policy must not be empty"):
        normalize_capture_overflow_policy("")

    with pytest.raises(ValueError, match=r"expected one of: raise/drop-oldest/drop-newest"):
        normalize_capture_overflow_policy("boom")

    with pytest.raises(TypeError, match=r"must be a str"):
        normalize_capture_overflow_policy(1)

    with pytest.raises(TypeError, match=r"must be a builtin str"):
        normalize_capture_overflow_policy(_StrSubclass("raise"))


def test_manager_policy_fields_are_builtin_str_after_pickle_roundtrip() -> None:
    hook_manager = HookManager(loader_result_policy="summary")
    restored_hook = pickle.loads(pickle.dumps(hook_manager))
    assert type(restored_hook.loader_result_policy) is str
    assert restored_hook.loader_result_policy == "summary"

    observer_manager = ObserverManager(mode="CAPTURE", capture_overflow_policy="drop_oldest", loader_result_policy="sample")
    restored_observer = pickle.loads(pickle.dumps(observer_manager))
    assert type(restored_observer.mode) is str
    assert restored_observer.mode == "capture"
    assert type(restored_observer.capture_overflow_policy) is str
    assert restored_observer.capture_overflow_policy == "drop-oldest"
    assert type(restored_observer.loader_result_policy) is str
    assert restored_observer.loader_result_policy == "sample"


def test_different_entrypoints_converge_to_same_normalized_policy_values() -> None:
    manager = HookManager(loader_result_policy=" SUMMARY ")
    options = ObservabilityOptions(loader_result_policy="SUMMARY")
    assert manager.loader_result_policy == "summary"
    assert options.loader_result_policy == "summary"

    manager2 = ObserverManager(mode=" CAPTURE ")
    assert manager2.mode == "capture"
