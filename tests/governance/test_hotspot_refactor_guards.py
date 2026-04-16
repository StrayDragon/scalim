import textwrap

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunSecurityOptions, RunOverrides, compile, run
from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter, LookupCastRegistry
from scalim.dsl.yaml_dsl.runtime.introspection import load_output_config
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.hooks import BaseHook, HookManager, IExecutionHook
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.viz import VizObserver, VizObserverConfig


def test_hotspot_public_imports_remain_available() -> None:
    assert DemandRunOptions is not None
    assert RunOverrides is not None
    assert run is not None
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


def test_external_consumer_style_yaml_compile_stays_supported(tmp_path) -> None:
    demand = tmp_path / "demand.yaml"
    demand.write_text(
        textwrap.dedent(
            """
            name: demo
            main_source:
              source_id: demo
              loader: tests.fixtures.mock_loaders.mock_loader
              fields:
                order_id: {extract: order_id}
            sources: {}
            """
        ).lstrip(),
        encoding="utf-8",
    )

    compilation = compile(
        str(demand),
        options=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures.mock_loaders"]))),
    )
    assert compilation is not None
