import pickle

from scalim.dsl.by_yaml import RunOverrides, run
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter, LookupCastRegistry
from scalim.dsl.by_yaml.runtime.introspection import load_output_config
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler, resolve_adaptive_max_workers
from scalim.hooks.base import BaseHook, HookManager, IExecutionHook
from scalim.ob.manager import ScalimObserverCaptureOverflowError, ObserverManager
from scalim.ob.presets.viz import VizEventEmitter, VizObserver, VizObserverConfig


def test_hotspot_stable_imports_expose_public_types() -> None:
    assert callable(run)
    assert RunOverrides is not None
    assert YamlDemandLoader is not None
    assert ConfigValidator is not None
    assert ConfigToIRConverter is not None
    assert LookupCastRegistry is not None
    assert load_output_config is not None
    assert AdaptiveLoadRefScheduler is not None
    assert callable(resolve_adaptive_max_workers)
    assert HookManager is not None
    assert BaseHook is not None
    assert IExecutionHook is not None
    assert ObserverManager is not None
    assert ScalimObserverCaptureOverflowError is not None
    assert VizObserver is not None
    assert VizObserverConfig is not None
    assert VizEventEmitter is not None


def test_hotspot_manager_pickle_roundtrip_keeps_runtime_shape() -> None:
    hook_manager = HookManager()
    restored_hook = pickle.loads(pickle.dumps(hook_manager))
    assert isinstance(restored_hook, HookManager)
    assert hasattr(restored_hook, "_lock")

    observer_manager = ObserverManager()
    restored_observer = pickle.loads(pickle.dumps(observer_manager))
    assert isinstance(restored_observer, ObserverManager)
    assert hasattr(restored_observer, "_lock")
