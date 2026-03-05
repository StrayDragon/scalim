import pickle
from types import MappingProxyType

from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.spec.ir.binding import BindingIr, LoaderIr


def _noop_loader():  # type: ignore[no-untyped-def]
    return {}


def _noop_params(ctx):  # type: ignore[no-untyped-def]
    _ = ctx
    return (), {}


def test_hook_manager_pickle_roundtrip_recreates_lock() -> None:
    manager = HookManager()

    restored = pickle.loads(pickle.dumps(manager))
    restored.register(BaseHook())
    restored.trigger_pipeline_start(targets=["x"], batch_size=1)


def test_observer_manager_pickle_roundtrip_recreates_lock() -> None:
    manager = ObserverManager()

    restored = pickle.loads(pickle.dumps(manager))
    restored.emit_pipeline_start(targets=["x"], batch_size=1)


def test_loader_ir_pickle_roundtrip_restores_mappingproxy_bindings() -> None:
    loader = LoaderIr(
        callable=_noop_loader,
        bindings={
            "id": BindingIr(
                key_field="id",
                params_builder=_noop_params,
            )
        },
    )
    assert isinstance(loader.bindings, MappingProxyType)

    restored = pickle.loads(pickle.dumps(loader))
    assert isinstance(restored.bindings, MappingProxyType)
    assert "id" in restored.bindings
