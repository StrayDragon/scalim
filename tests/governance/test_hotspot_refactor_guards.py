from scalim.dsl.by_yaml import RunOverrides, run
from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter, LookupCastRegistry
from scalim.dsl.by_yaml.runtime.introspection import load_output_config
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.hooks import BaseHook, HookManager, IExecutionHook
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.viz import VizObserver, VizObserverConfig


def test_hotspot_public_imports_remain_available() -> None:
    assert RunOverrides is not None
    assert run is not None
    assert YamlDemandLoader is not None
    assert ConfigToIRConverter is not None
    assert LookupCastRegistry is not None
    assert load_output_config is not None
    assert IExecutionHook is not None
    assert BaseHook is not None
    assert HookManager is not None
    assert ObserverManager is not None
    assert VizObserverConfig is not None
    assert VizObserver is not None
    assert AdaptiveLoadRefScheduler is not None


def test_external_consumer_style_yaml_imports_stay_supported() -> None:
    loader = YamlDemandLoader()
    converter = ConfigToIRConverter.from_allowlist(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))

    assert loader is not None
    assert converter is not None
    assert callable(load_output_config)
