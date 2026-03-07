import pickle

from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager


def test_manager_phase1_public_imports_remain_available() -> None:
    assert HookManager is not None
    assert ObserverManager is not None


def test_manager_phase1_pickle_roundtrip_restores_runtime_caches() -> None:
    hook_manager = HookManager()
    restored_hook_manager = pickle.loads(pickle.dumps(hook_manager))
    assert isinstance(restored_hook_manager, HookManager)
    assert hasattr(restored_hook_manager, "_lock")
    assert isinstance(restored_hook_manager._typed_handlers_by_event_type, dict)
    assert isinstance(restored_hook_manager._on_event_handlers_by_event_type, dict)

    observer_manager = ObserverManager()
    restored_observer_manager = pickle.loads(pickle.dumps(observer_manager))
    assert isinstance(restored_observer_manager, ObserverManager)
    assert hasattr(restored_observer_manager, "_lock")
    assert isinstance(restored_observer_manager._observers_by_event_type, dict)
    assert isinstance(restored_observer_manager._observers_for_unknown_event_type, tuple)
