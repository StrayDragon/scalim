import pickle
from types import MappingProxyType

from scalim.spec.ir import ComputeCallContextIr, DemandIr, FieldIr, KeyIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import BindingIr, LoaderIr


def test_source_ir_pickle_roundtrip_restores_mappingproxy_bindings() -> None:
    binding = BindingIr(
        key_field="id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="noop.params_builder.id"),
    )
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="noop.loader")),
        bindings={"id": binding},
    )
    assert isinstance(source.bindings, MappingProxyType)

    restored = pickle.loads(pickle.dumps(source))
    assert isinstance(restored.bindings, MappingProxyType)
    assert "id" in restored.bindings


def test_source_ir_getstate_does_not_force_convert_when_bindings_not_mappingproxy() -> None:
    binding = BindingIr(
        key_field="id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="noop.params_builder.id"),
    )
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="noop.loader")),
        bindings={"id": binding},
    )
    object.__setattr__(source, "bindings", {"id": binding})

    state = source.__getstate__()
    assert state["bindings"] == {"id": binding}


def test_demand_ir_pickle_roundtrip_restores_mappingproxy_sources_and_fields() -> None:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(field_id="id", name="ID", source=main_source)
    demand = DemandIr(sources={"s1": source}, fields={"id": field}, main_source=main_source)
    assert isinstance(demand.sources, MappingProxyType)
    assert isinstance(demand.fields, MappingProxyType)

    restored = pickle.loads(pickle.dumps(demand))
    assert isinstance(restored.sources, MappingProxyType)
    assert isinstance(restored.fields, MappingProxyType)
    assert isinstance(restored.sources["s1"].bindings, MappingProxyType)
    assert "s1" in restored.sources
    assert "id" in restored.fields


def test_demand_ir_getstate_does_not_force_convert_when_sources_and_fields_not_mappingproxy() -> None:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    field = FieldIr(field_id="id", name="ID", source=main_source)
    demand = DemandIr(sources={"s1": source}, fields={"id": field}, main_source=main_source)
    object.__setattr__(demand, "sources", {"s1": source})
    object.__setattr__(demand, "fields", {"id": field})

    state = demand.__getstate__()
    assert state["sources"] == {"s1": source}
    assert state["fields"] == {"id": field}


def test_compute_call_context_ir_pickle_roundtrip_restores_mappingproxy_values() -> None:
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=2,
        field_id="x",
        deps=("a", "b"),
        values={"a": 1, "b": None},
    )
    assert isinstance(ctx.values, MappingProxyType)

    restored = pickle.loads(pickle.dumps(ctx))
    assert isinstance(restored.values, MappingProxyType)
    assert restored.values["a"] == 1


def test_compute_call_context_ir_getstate_does_not_force_convert_when_values_not_mappingproxy() -> None:
    ctx = ComputeCallContextIr(
        row_id=1,
        batch_num=2,
        field_id="x",
        deps=(),
        values={"a": 1},
    )
    object.__setattr__(ctx, "values", {"a": 1})

    state = ctx.__getstate__()
    assert state["values"] == {"a": 1}
