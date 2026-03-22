"""Executor operator tests: load_ref."""

from typing import Dict, List

import pytest

from scalim.events.catalog import EVENT_LOADER_CALL
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref import loader as load_ref_loader
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import LoadRefCacheEntry
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.ob.presets.relations import RelationConfig, RelationObserver
from scalim.planning.operators import LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, SourceIr

from .fixtures.executor_operator_fixtures import (
    _FailLoader,
    _SampleLoader,
    _Target,
    _make_main_source,
    _make_runtime,
    _raise_type_error,
    _raise_value_error,
)


@pytest.mark.parametrize(
    ("main_source", "lookup_steps"),
    [
        (_make_main_source(), ()),
        (
            None,
            (
                LookupStepIr(
                    from_field="fk_id",
                    to_source=SourceIr(source_id="customers", key=KeyIr(key="customer_id"), loader_spec=LoaderIr(callable=lambda: {})),
                ),
            ),
        ),
    ],
    ids=[
        "empty_steps",
        "missing_main_source",
    ],
)
def test_load_ref_returns_early_variants(main_source, lookup_steps) -> None:  # type: ignore[no-untyped-def]
    source = SourceIr(source_id="customers", key=KeyIr(key="customer_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="customer_name", name="Name", source=source)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="customer_name",
        field_spec=field_spec,
        lookup_steps=lookup_steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"customer_name": field_spec}), main_source)
    context = BatchContext()
    context.set_field_value("fk_id", 1, 10)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("customer_name", 1) is None


def test_load_ref_builds_batch_rows_with_row_binding() -> None:
    captured: Dict[str, object] = {}

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        captured["batch_rows"] = ctx.batch_rows
        return (), {"rows": ctx.batch_rows}

    def _loader(rows):  # type: ignore[no-untyped-def]
        captured["rows_param"] = rows
        return {1: {"name": "Alpha"}}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder, mode="rows")
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    context.set_field_value("note", 1, "n1")

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert captured["batch_rows"] == [{"fk_id": 1, "note": "n1"}]
    assert captured["rows_param"] == [{"fk_id": 1, "note": "n1"}]
    assert context.get_field_value("target_name", 1) == "Alpha"


def test_load_ref_rows_cache_does_not_retain_batch_rows_in_cache() -> None:
    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"rows": ctx.batch_rows}

    def _loader(rows):  # type: ignore[no-untyped-def]
        assert rows is not None
        return {1: {"name": "Alpha"}}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder, mode="rows", cache_mode="batch")
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()
    context.set_field_value("fk_id", 1, 1)
    context.set_field_value("note", 1, "n1")

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert runtime.load_ref_cache
    assert all(entry.batch_rows is None for entry in runtime.load_ref_cache.values())


def test_load_ref_cache_hit_uses_cached_batch_rows_in_context() -> None:
    class _CaptureLoaderCallObserver(Observer):
        event_types = {EVENT_LOADER_CALL}

        def __init__(self) -> None:
            self.events: List[object] = []

        def on_event(self, event) -> None:  # type: ignore[override]
            self.events.append(event)

    runtime = _make_runtime(ExecutionPlan(), _make_main_source())
    observer = _CaptureLoaderCallObserver()
    runtime.observer_manager.register(observer)

    cache_key = (("targets", ("fk_id",), "target_id", None, None), frozenset([1]))
    cached_batch_rows = [{"fk_id": 1, "note": "n1"}]
    cached_result = {1: {"name": "Alpha"}}
    runtime.load_ref_cache[cache_key] = LoadRefCacheEntry(result=cached_result, batch_rows=cached_batch_rows)
    binding = BindingIr(key_field="target_id", params_builder=lambda ctx: ((), {"rows": ctx.batch_rows}), mode="rows")

    loader_context = LoaderCallContextIr(
        batch_row_nth=[0],
        source_id="targets",
        field_keys=["target_name"],
        is_ref_loader=True,
        lookup_keys={1},
        lookup_keys_list=[1],
        batch_rows=None,
    )

    result = load_ref_loader._get_cached_ref_result(
        runtime=runtime,
        cache_key=cache_key,
        binding=binding,
        loader_context=loader_context,
        lookup_key_count=1,
        event_field_keys=("target_name",),
        source_id="targets",
    )

    assert result == cached_result
    assert observer.events
    captured_event = observer.events[-1]
    assert captured_event.payload.params["rows"] == cached_batch_rows


def test_load_ref_lookup_chunking_splits_calls() -> None:
    calls: List[List[int]] = []

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"order_ids": list(ctx.lookup_keys or [])}

    def _loader(order_ids):  # type: ignore[no-untyped-def]
        calls.append(list(order_ids))
        return {key: {"name": "Name{}".format(key)} for key in order_ids}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
        lookup_chunk_size=2,
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder)
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()

    for row_id in [1, 2, 3, 4, 5]:
        context.set_field_value("fk_id", row_id, row_id)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2, 3, 4, 5], runtime)

    assert len(calls) == 3
    assert sorted(len(call) for call in calls) == [1, 2, 2]
    assert context.get_field_value("target_name", 1) == "Name1"
    assert context.get_field_value("target_name", 2) == "Name2"
    assert context.get_field_value("target_name", 3) == "Name3"
    assert context.get_field_value("target_name", 4) == "Name4"
    assert context.get_field_value("target_name", 5) == "Name5"


def test_load_ref_lookup_chunking_disabled_by_default() -> None:
    calls: List[List[int]] = []

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"order_ids": list(ctx.lookup_keys or [])}

    def _loader(order_ids):  # type: ignore[no-untyped-def]
        calls.append(list(order_ids))
        return {key: {"name": "Name{}".format(key)} for key in order_ids}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder)
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()

    for row_id in [1, 2, 3]:
        context.set_field_value("fk_id", row_id, row_id)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert len(calls) == 1


def test_load_ref_skips_missing_multi_field_fk() -> None:
    main_source = _make_main_source()
    target_source = SourceIr(source_id="targets", key=KeyIr(key="target_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (LookupStepIr(from_field=("region_id", "store_id"), to_source=target_source),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()
    context.set_field_value("region_id", 1, "r1")
    context.set_field_value("store_id", 1, None)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("target_name", 1) is None


def test_load_ref_multi_field_next_step_and_object_result() -> None:
    main_source = _make_main_source()
    mapping_source = SourceIr(source_id="mapping", key=KeyIr(key="fk_id"), loader_spec=LoaderIr(callable=_FailLoader()))
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key=("region_id", "store_id")),
        loader_spec=LoaderIr(callable=_FailLoader()),
    )
    field_spec = FieldIr(
        field_id="target_name",
        name="Target",
        source=target_source,
        data_key="name",
        transform=lambda value: value.upper() if value else value,
    )
    steps = (
        LookupStepIr(from_field="fk_id", to_source=mapping_source),
        LookupStepIr(from_field=("region_id", "store_id"), to_source=target_source),
    )
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    runtime.preloaded_cache = {
        "mapping": {
            10: {"region_id": "r1", "store_id": "s1"},
            20: {"region_id": "r2"},
        },
        "targets": {
            ("r1", "s1"): _Target("alpha"),
        },
    }

    context = BatchContext()
    context.set_field_value("fk_id", 1, 10)
    context.set_field_value("fk_id", 2, 20)
    context.set_field_value("fk_id", 3, 30)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert context.get_field_value("target_name", 1) == "ALPHA"
    assert context.get_field_value("target_name", 2) is None
    assert context.get_field_value("target_name", 3) is None


def test_load_ref_handles_list_to_field_binding_key() -> None:
    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key=("region_id", "store_id")),
        loader_spec=LoaderIr(callable=_FailLoader()),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (
        LookupStepIr(
            from_field=("region_id", "store_id"),
            to_source=target_source,
            to_field=["region_id", "store_id"],
        ),
    )
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    runtime.preloaded_cache = {"targets": {("r1", "s1"): {"target_name": "alpha"}}}

    context = BatchContext()
    context.set_field_value("region_id", 1, "r1")
    context.set_field_value("store_id", 1, "s1")

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("target_name", 1) == "alpha"


def test_load_ref_breaks_when_lookup_keys_empty() -> None:
    main_source = _make_main_source()
    mapping_source = SourceIr(source_id="mapping", key=KeyIr(key="fk_id"), loader_spec=LoaderIr(callable=_FailLoader()))
    target_source = SourceIr(source_id="targets", key=KeyIr(key="target_id"), loader_spec=LoaderIr(callable=_FailLoader()))
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (
        LookupStepIr(from_field="fk_id", to_source=mapping_source),
        LookupStepIr(from_field=("region_id", "store_id"), to_source=target_source),
    )
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    runtime.preloaded_cache = {
        "mapping": {
            10: {"region_id": "r1"},
        },
    }

    context = BatchContext()
    context.set_field_value("fk_id", 1, 10)
    context.set_field_value("fk_id", 2, 20)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("target_name", 1) is None
    assert context.get_field_value("target_name", 2) is None


def test_load_ref_write_final_step_missing_field_spec() -> None:
    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"value_ids": list(ctx.lookup_keys or [])}

    def _loader(value_ids):  # type: ignore[no-untyped-def]
        return {value_id: {"value": "v{}".format(value_id)} for value_id in value_ids}

    main_source = _make_main_source()
    binding = BindingIr(key_field="value_id", params_builder=_params_builder)
    loader_spec = LoaderIr(callable=_loader, bindings={"value_id": binding})
    target_source = SourceIr(source_id="values", key=KeyIr(key="value_id"), loader_spec=loader_spec)
    field_spec = FieldIr(field_id="value", name="Value", source=target_source)

    step = LookupStepIr(from_field="value_id", to_source=target_source)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="value",
        field_spec=field_spec,
        lookup_steps=(step,),
    )

    runtime = _make_runtime(ExecutionPlan(operators=(operator,), field_specs={}), main_source)
    context = BatchContext()
    context.set_field_value("value_id", 1, 1)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("value", 1) == "v1"


def test_load_ref_normalize_cache_reuses_lookup_cast_per_relation() -> None:
    loader = _SampleLoader()
    cast_calls: List[Any] = []

    def _counting_cast(value):  # type: ignore[no-untyped-def]
        cast_calls.append(value)
        return value

    binding = BindingIr(
        key_field="order_id",
        params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys or [])}),
    )
    loader_spec = LoaderIr(callable=loader.get_orders, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source, lookup_cast=_counting_cast)
    field_amount = FieldIr(field_id="amount", name="Amount", source=source, lookup_steps=(step,))
    field_extra = FieldIr(field_id="extra", name="Extra", source=source, lookup_steps=(step,))

    op_amount = LoadRefOperatorIr(
        operator_id="load_ref_0",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_amount,
        lookup_steps=(step,),
    )
    op_extra = LoadRefOperatorIr(
        operator_id="load_ref_1",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="extra",
        field_spec=field_extra,
        lookup_steps=(step,),
    )

    plan = ExecutionPlan(operators=(op_amount, op_extra), field_specs={"amount": field_amount, "extra": field_extra})
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_amount, context, [1, 2], runtime)
    executor.execute(op_extra, context, [1, 2], runtime)

    assert len(cast_calls) == 2
    assert context.get_field_value("amount", 1) == 10
    assert context.get_field_value("extra", 2) == "y"


def test_load_ref_normalize_cache_skips_different_relation() -> None:
    loader = _SampleLoader()
    cast_a_calls: List[Any] = []
    cast_b_calls: List[Any] = []

    def _cast_a(value):  # type: ignore[no-untyped-def]
        cast_a_calls.append(value)
        return value

    def _cast_b(value):  # type: ignore[no-untyped-def]
        cast_b_calls.append(value)
        return value

    binding = BindingIr(
        key_field="order_id",
        params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys or [])}),
    )
    loader_spec = LoaderIr(callable=loader.get_orders, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step_a = LookupStepIr(from_field="order_id", to_source=source, lookup_cast=_cast_a)
    step_b = LookupStepIr(from_field="order_id", to_source=source, lookup_cast=_cast_b)
    field_amount = FieldIr(field_id="amount", name="Amount", source=source, lookup_steps=(step_a,))
    field_extra = FieldIr(field_id="extra", name="Extra", source=source, lookup_steps=(step_b,))

    op_amount = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_amount,
        lookup_steps=(step_a,),
    )
    op_extra = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="extra",
        field_spec=field_extra,
        lookup_steps=(step_b,),
    )

    plan = ExecutionPlan(operators=(op_amount, op_extra), field_specs={"amount": field_amount, "extra": field_extra})
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_amount, context, [1, 2], runtime)
    executor.execute(op_extra, context, [1, 2], runtime)

    assert len(cast_a_calls) == 2
    assert len(cast_b_calls) == 2


def test_load_ref_normalize_cache_dedupes_diagnostics() -> None:
    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable=_FailLoader()),
    )
    step = LookupStepIr(from_field="customer_id", to_source=target_source, lookup_cast=_raise_value_error)
    field_a = FieldIr(field_id="name_a", name="NameA", source=target_source, lookup_steps=(step,))
    field_b = FieldIr(field_id="name_b", name="NameB", source=target_source, lookup_steps=(step,))

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="name_a",
        field_spec=field_a,
        lookup_steps=(step,),
    )
    op_b = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="name_b",
        field_spec=field_b,
        lookup_steps=(step,),
    )

    relation_observer = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
    observer_manager = ObserverManager(observers=[relation_observer])
    runtime = _make_runtime(
        ExecutionPlan(operators=(op_a, op_b), field_specs={"name_a": field_a, "name_b": field_b}),
        main_source,
        observer_manager=observer_manager,
    )
    context = BatchContext()
    context.set_field_value("customer_id", 1, "bad")

    executor = LoadRefOperatorExecutor()
    executor.execute(op_a, context, [1], runtime)
    executor.execute(op_b, context, [1], runtime)

    metrics = relation_observer.metrics
    assert metrics.total_lookups == 1
    assert metrics.type_mismatch_count == 1


def test_load_ref_records_relation_observability() -> None:
    def _load_customers():  # type: ignore[no-untyped-def]
        return {100: {"name": "Alice"}}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable=_load_customers),
    )
    field_spec = FieldIr(field_id="customer_name", name="Name", source=target_source, data_key="name")
    steps = (LookupStepIr(from_field="customer_id", to_source=target_source),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="customer_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )

    relation_observer = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
    observer_manager = ObserverManager(observers=[relation_observer])
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"customer_name": field_spec}),
        main_source,
        observer_manager=observer_manager,
    )
    context = BatchContext()
    context.set_field_value("customer_id", 1, 100)
    context.set_field_value("customer_id", 2, 200)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2, 3], runtime)

    assert context.get_field_value("customer_name", 1) == "Alice"
    assert context.get_field_value("customer_name", 2) is None
    assert context.get_field_value("customer_name", 3) is None

    metrics = relation_observer.metrics
    assert metrics.total_lookups == 3
    assert metrics.hit_count == 1
    assert metrics.miss_count == 1
    assert metrics.null_key_count == 1


def test_load_ref_records_relation_type_error() -> None:
    main_source = _make_main_source()
    target_source = SourceIr(source_id="customers", key=KeyIr(key="customer_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="customer_name", name="Name", source=target_source)
    steps = (LookupStepIr(from_field="customer_id", to_source=target_source, lookup_cast=_raise_value_error),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="customer_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )

    relation_observer = RelationObserver(config=RelationConfig(sampling_rate=1.0, report_format="none"))
    observer_manager = ObserverManager(observers=[relation_observer])
    runtime = _make_runtime(
        ExecutionPlan(field_specs={"customer_name": field_spec}),
        main_source,
        observer_manager=observer_manager,
    )
    context = BatchContext()
    context.set_field_value("customer_id", 1, "bad")

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    metrics = relation_observer.metrics
    assert metrics.total_lookups == 1
    assert metrics.type_mismatch_count == 1


def test_load_ref_multi_field_first_step_type_error() -> None:
    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key=("region_id", "store_id")),
        loader_spec=LoaderIr(callable=lambda: {}),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (LookupStepIr(from_field=("region_id", "store_id"), to_source=target_source, lookup_cast=_raise_value_error),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    context = BatchContext()
    context.set_field_value("region_id", 1, "r1")
    context.set_field_value("store_id", 1, "s1")

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("target_name", 1) is None


def test_load_ref_next_step_single_field_errors() -> None:
    main_source = _make_main_source()
    mapping_source = SourceIr(source_id="mapping", key=KeyIr(key="map_id"), loader_spec=LoaderIr(callable=lambda: {}))
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id", cast=_raise_value_error),
        loader_spec=LoaderIr(callable=_FailLoader()),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (
        LookupStepIr(from_field="map_id", to_source=mapping_source),
        LookupStepIr(from_field="target_id", to_source=target_source),
    )
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    runtime.preloaded_cache = {
        "mapping": {
            10: {"target_id": "bad"},
            20: {"other": "missing"},
        },
    }
    context = BatchContext()
    context.set_field_value("map_id", 1, 20)
    context.set_field_value("map_id", 2, 10)

    LoadRefOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("target_name", 1) is None
    assert context.get_field_value("target_name", 2) is None


def test_load_ref_next_step_multi_field_type_error() -> None:
    main_source = _make_main_source()
    mapping_source = SourceIr(source_id="mapping", key=KeyIr(key="map_id"), loader_spec=LoaderIr(callable=lambda: {}))
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key=("region_id", "store_id"), cast=_raise_value_error),
        loader_spec=LoaderIr(callable=_FailLoader()),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source)
    steps = (
        LookupStepIr(from_field="map_id", to_source=mapping_source),
        LookupStepIr(from_field=("region_id", "store_id"), to_source=target_source),
    )
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source)
    runtime.preloaded_cache = {
        "mapping": {
            10: {"region_id": "r1", "store_id": "s1"},
        },
    }
    context = BatchContext()
    context.set_field_value("map_id", 1, 10)

    LoadRefOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("target_name", 1) is None


def test_load_ref_uses_cached_sources_and_multi_field() -> None:
    main_source = _make_main_source()

    mapping_loader = _FailLoader()
    mapping_source = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "store_id")),
        loader_spec=LoaderIr(callable=mapping_loader),
    )

    country_loader = _FailLoader()

    def _country_extract(pk, result):  # type: ignore[no-untyped-def]
        return {"country_name": result[pk]["name"]}

    countries_source = SourceIr(
        source_id="countries",
        key=KeyIr(key="country_id"),
        loader_spec=LoaderIr(callable=country_loader, extractor=_country_extract),
    )

    field_spec = FieldIr(
        field_id="country_name",
        name="Country",
        source=countries_source,
        transform=lambda value: value.upper() if value else value,
    )

    steps = (
        LookupStepIr(from_field=("region_id", "store_id"), to_source=mapping_source),
        LookupStepIr(from_field="country_id", to_source=countries_source),
    )

    operator = LoadRefOperatorIr(
        operator_id="load_ref_country",
        operator_type=OperatorType.LOAD_REF.value,
        source=countries_source,
        field_key="country_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )

    plan = ExecutionPlan(field_specs={"country_name": field_spec}, target_fields=["country_name"])
    runtime = _make_runtime(plan, main_source)
    runtime.preloaded_cache = {
        "mapping": {
            ("r1", "s1"): {"country_id": "C1"},
            ("r2", "s2"): {"country_id": "C2"},
        },
        "countries": {
            "C1": {"name": "China"},
            "C2": {"name": "Japan"},
        },
    }

    context = BatchContext()
    context.set_field_value("region_id", 1, "r1")
    context.set_field_value("store_id", 1, "s1")
    context.set_field_value("region_id", 2, "r2")
    context.set_field_value("store_id", 2, "s2")

    LoadRefOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("country_name", 1) == "CHINA"
    assert context.get_field_value("country_name", 2) == "JAPAN"
    assert mapping_loader.calls == 0
    assert country_loader.calls == 0


def test_load_ref_execute_returns_early_for_non_load_ref_operator() -> None:
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=lambda: {}))
    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount",),
        is_primary=True,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={}), _make_main_source())

    LoadRefOperatorExecutor().execute(operator, BatchContext(), [1], runtime)


def test_load_ref_executor_ignores_non_load_ref_operator() -> None:
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    runtime = _make_runtime(ExecutionPlan(field_specs={"amount": field_spec}), _make_main_source())
    context = BatchContext()

    wrong_operator = LoadOperatorIr(
        operator_id="load",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount",),
        is_primary=False,
    )

    LoadRefOperatorExecutor().execute(wrong_operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None


def test_load_ref_key_normalization_auto_str_unifies_key_types_for_matching() -> None:
    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        # Always return string-keyed mapping (regardless of input type).
        return {str(key): {"name": "Name{}".format(key)} for key in target_ids}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder)
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    plan = ExecutionPlan(field_specs={"target_name": field_spec})

    # raw: fk=1 -> lookup key is int(1), but mapping is str-keyed -> miss
    runtime_raw = _make_runtime(plan, main_source, key_normalization="raw")
    ctx_raw = BatchContext()
    ctx_raw.set_field_value("fk_id", 1, 1)
    LoadRefOperatorExecutor().execute(operator, ctx_raw, [1], runtime_raw)
    assert ctx_raw.get_field_value("target_name", 1) is None

    # auto_str: fk=1 -> lookup key is "1", mapping is str-keyed -> hit
    runtime_norm = _make_runtime(plan, main_source, key_normalization="auto_str")
    ctx_norm = BatchContext()
    ctx_norm.set_field_value("fk_id", 1, 1)
    LoadRefOperatorExecutor().execute(operator, ctx_norm, [1], runtime_norm)
    assert ctx_norm.get_field_value("target_name", 1) == "Name1"


def test_load_ref_key_normalization_force_str_normalizes_even_when_lookup_cast_is_set() -> None:
    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"target_ids": list(ctx.lookup_keys_list or [])}

    def _loader(target_ids):  # type: ignore[no-untyped-def]
        # Return mapping keyed by whatever the loader received.
        return {key: {"name": "Name{}".format(key)} for key in target_ids}

    main_source = _make_main_source()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    binding = BindingIr(key_field="target_id", params_builder=_params_builder)
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding, lookup_cast=int),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    plan = ExecutionPlan(field_specs={"target_name": field_spec})

    # auto_str: explicit lookup_cast takes precedence -> loader sees int keys
    runtime_auto = _make_runtime(plan, main_source, key_normalization="auto_str")
    ctx_auto = BatchContext()
    ctx_auto.set_field_value("fk_id", 1, "1")
    LoadRefOperatorExecutor().execute(operator, ctx_auto, [1], runtime_auto)
    assert ctx_auto.get_field_value("target_name", 1) == "Name1"

    # force_str: normalize at the final match boundary -> loader sees str keys
    runtime_force = _make_runtime(plan, main_source, key_normalization="force_str")
    ctx_force = BatchContext()
    ctx_force.set_field_value("fk_id", 1, "1")
    LoadRefOperatorExecutor().execute(operator, ctx_force, [1], runtime_force)
    assert ctx_force.get_field_value("target_name", 1) == "Name1"

    # Verify the key space difference via cached loader results.
    assert 1 in next(iter(runtime_auto.load_ref_cache.values())).result
    assert "1" in next(iter(runtime_force.load_ref_cache.values())).result


def test_load_ref_cached_mapping_key_normalization_hits_preloaded_int_key() -> None:
    main_source = _make_main_source()
    fail_loader = _FailLoader()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=fail_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source, key_normalization="auto_str")
    runtime.preloaded_cache["targets"] = {1: {"name": "Alpha"}}
    ctx = BatchContext()
    ctx.set_field_value("fk_id", 1, "1")

    LoadRefOperatorExecutor().execute(operator, ctx, [1], runtime)

    assert fail_loader.calls == 0
    assert ctx.get_field_value("target_name", 1) == "Alpha"


def test_load_ref_cached_mapping_key_normalization_hits_preloaded_multi_field_key() -> None:
    main_source = _make_main_source()
    fail_loader = _FailLoader()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key=("a", "b")),
        loader_spec=LoaderIr(callable=fail_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    steps = (LookupStepIr(from_field=["a", "b"], to_source=target_source),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source, key_normalization="auto_str")
    runtime.preloaded_cache["targets"] = {(1, 2): {"name": "Alpha"}}
    ctx = BatchContext()
    ctx.set_field_value("a", 1, "1")
    ctx.set_field_value("b", 1, 2)

    LoadRefOperatorExecutor().execute(operator, ctx, [1], runtime)

    assert fail_loader.calls == 0
    assert ctx.get_field_value("target_name", 1) == "Alpha"


def test_load_ref_cached_mapping_key_normalization_collision_fail_fast() -> None:
    main_source = _make_main_source()
    fail_loader = _FailLoader()
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable=fail_loader),
    )
    field_spec = FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source),)
    operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=target_source,
        field_key="target_name",
        field_spec=field_spec,
        lookup_steps=steps,
    )
    runtime = _make_runtime(ExecutionPlan(field_specs={"target_name": field_spec}), main_source, key_normalization="auto_str")
    runtime.preloaded_cache["targets"] = {1: {"name": "A"}, "1": {"name": "B"}}
    ctx = BatchContext()
    ctx.set_field_value("fk_id", 1, 1)

    with pytest.raises(ValueError, match="collision"):
        LoadRefOperatorExecutor().execute(operator, ctx, [1], runtime)
