import pytest

from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import KeyIr, LookupCastSpecIr, LookupStepIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir.lookup_casts import lookup_cast_id


def _make_runtime(*, key_normalization: str) -> ExecutionRuntime:
    plan = ExecutionPlan(field_specs={})
    runtime_bindings = RuntimeBindings(main_source_loaders={"orders": lambda: []})
    int_cast = LookupCastSpecIr(name="int")
    runtime_bindings.lookup_key_casts[lookup_cast_id(int_cast, is_multi=False)] = lambda value: int(value) if value is not None else None
    return ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader")),
        sources={},
        runtime_bindings=runtime_bindings,
        key_normalization=key_normalization,  # type: ignore[arg-type]
    )


def _make_step(*, lookup_cast: "LookupCastSpecIr | None" = None) -> LookupStepIr:
    source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="targets.loader")),
    )
    return LookupStepIr(from_field="fk", to_source=source, lookup_cast=lookup_cast)


def test_execution_runtime_normalize_lookup_key_status_auto_str_ok_type_error_and_null_key() -> None:
    runtime = _make_runtime(key_normalization="auto_str")
    step = _make_step()

    key, status, message = runtime.normalize_lookup_key_with_status(1, step)
    assert (key, status, message) == ("1", "ok", None)

    raw = object()
    key2, status2, message2 = runtime.normalize_lookup_key_with_status(raw, step)
    assert key2 is None
    assert status2 == "type_error"
    assert message2 is not None
    assert "type=object" in message2
    assert "0x" not in message2

    key3, status3, message3 = runtime.normalize_lookup_key_with_status((1, None), step)
    assert (key3, status3, message3) == (None, "null_key", None)


def test_execution_runtime_normalize_lookup_key_status_explicit_cast_precedence_and_force_str() -> None:
    step = _make_step(lookup_cast=LookupCastSpecIr(name="int"))

    runtime_auto = _make_runtime(key_normalization="auto_str")
    key, status, _message = runtime_auto.normalize_lookup_key_with_status("1", step)
    assert (key, status) == (1, "ok")

    runtime_force = _make_runtime(key_normalization="force_str")
    key2, status2, _message2 = runtime_force.normalize_lookup_key_with_status("1", step)
    assert (key2, status2) == ("1", "ok")


def test_execution_runtime_get_cached_source_mapping_branches() -> None:
    raw_mapping = {1: {"name": "Alpha"}}
    step = _make_step()

    runtime_raw = _make_runtime(key_normalization="raw")
    runtime_raw.preloaded_cache["targets"] = raw_mapping
    assert runtime_raw.get_cached_source_mapping(step) is raw_mapping

    runtime_norm = _make_runtime(key_normalization="auto_str")
    runtime_norm.preloaded_cache["targets"] = {1: {"name": "Alpha"}, object(): {"name": "SkipMe"}}
    view1 = runtime_norm.get_cached_source_mapping(step)
    view2 = runtime_norm.get_cached_source_mapping(step)
    assert view1 is view2
    assert "1" in view1
    assert 1 not in view1

    runtime_missing = _make_runtime(key_normalization="auto_str")
    with pytest.raises(KeyError, match="Unknown cached source"):
        _ = runtime_missing.get_cached_source_mapping(step)


def test_execution_runtime_get_cached_source_mapping_collision_fails_fast_when_value_equality_raises() -> None:
    class _ExplodingEq(object):
        def __eq__(self, _other) -> bool:  # type: ignore[override]
            raise RuntimeError("boom")

    runtime = _make_runtime(key_normalization="auto_str")
    step = _make_step()
    runtime.preloaded_cache["targets"] = {123: _ExplodingEq(), "123": _ExplodingEq()}

    with pytest.raises(ValueError, match="collision") as excinfo:
        _ = runtime.get_cached_source_mapping(step)

    assert "123" not in str(excinfo.value)
