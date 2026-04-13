import pytest
import pickle
from collections import UserDict
from types import MappingProxyType

from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.spec.ir import RuntimeHandleIdIr
from scalim.spec.ir.binding import BindingIr, LoaderIr, _restore_bindings


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
        callable_ref=RuntimeHandleIdIr(handle_id="noop.loader"),
        bindings={
            "id": BindingIr(
                key_field="id",
                params_builder_ref=RuntimeHandleIdIr(handle_id="noop.params_builder.id"),
            )
        },
    )
    assert isinstance(loader.bindings, MappingProxyType)

    restored = pickle.loads(pickle.dumps(loader))
    assert isinstance(restored.bindings, MappingProxyType)
    assert "id" in restored.bindings


def test_restore_bindings_returns_none_for_non_dict() -> None:
    assert _restore_bindings([("id", object())]) is None


def test_restore_bindings_rejects_non_string_tuple_key_items() -> None:
    binding = BindingIr(key_field="id", params_builder_ref=RuntimeHandleIdIr(handle_id="noop.params_builder.id"))
    with pytest.raises(TypeError, match="Invalid binding key"):
        _restore_bindings({("id", 1): binding})


def test_restore_bindings_rejects_invalid_value() -> None:
    with pytest.raises(TypeError, match="Invalid binding value"):
        _restore_bindings({"id": object()})


def test_loader_ir_state_helpers_cover_non_mappingproxy_and_restore_none() -> None:
    binding = BindingIr(key_field="id", params_builder_ref=RuntimeHandleIdIr(handle_id="noop.params_builder.id"))
    bindings = UserDict({"id": binding})
    loader = LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="noop.loader"), bindings=bindings)  # type: ignore[arg-type]

    state = loader.__getstate__()
    assert state["bindings"] is bindings

    restored = LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="noop.loader2"))
    restored.__setstate__({"callable_ref": restored.callable_ref, "bindings": [("id", binding)]})  # type: ignore[arg-type]
    assert restored.bindings == [("id", binding)]  # type: ignore[comparison-overlap]
