"""Executor operator tests: load."""

import pytest

from scalim.execution.context import BatchContext
from scalim.events import Event, EventType
from scalim.execution.executor.operators.load import LoadOperatorExecutor
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.operators import LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import FieldIr, KeyIr, LookupCastSpecIr, LookupStepIr, RuntimeHandleIdIr, SourceIr, SourceNormalizeIr, ValueOpIr
from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir.lookup_casts import lookup_cast_id
from scalim.hooks import BaseHook

from tests.fixtures.executor_operator_fixtures import (
    _Order,
    _Runtime,
    _SampleLoader,
    _WantsInstrumentation,
    _make_main_source,
    _make_runtime,
    _raise_type_error,
    _raise_value_error,
)


def test_load_operator_build_loader_call_kwargs_is_wants_gated() -> None:
    runtime_bindings = RuntimeBindings()

    def _params_builder(ctx: LoaderCallContextIr):  # type: ignore[no-untyped-def]
        return (), {"src": ctx.source_id}

    runtime_bindings.params_builders[("main", "k")] = _params_builder
    binding = BindingIr(key_field="k", params_builder_ref=RuntimeHandleIdIr(handle_id="params_builder:main:k"))
    loader_context = LoaderCallContextIr(source_id="main")
    runtime = _Runtime(_WantsInstrumentation(EventType.LOADER_CALL), runtime_bindings=runtime_bindings)

    executor = LoadOperatorExecutor()
    assert executor._build_loader_call_kwargs(runtime, binding, loader_context) == {"src": "main"}  # noqa: SLF001


def test_load_operator_maybe_emit_loader_slim_extracts_key_count() -> None:
    instrumentation = _WantsInstrumentation(EventType.LOADER_SLIM)
    runtime = _Runtime(instrumentation, batch_num=7)
    executor = LoadOperatorExecutor()

    result = {"row1": {"a": 1, "b": 2, "c": 3}}
    executor._maybe_emit_loader_slim(runtime, loader_name="demo", result=result, field_keys=["a"])  # noqa: SLF001

    assert instrumentation.loader_slim_calls == [
        {
            "loader_name": "demo",
            "original_keys": 3,
            "extracted_fields": ["a"],
            "batch_num": 7,
        }
    ]


def test_load_operator_maybe_emit_loader_slim_handles_empty_and_non_mapping_values() -> None:
    instrumentation = _WantsInstrumentation(EventType.LOADER_SLIM)
    runtime = _Runtime(instrumentation, batch_num=1)
    executor = LoadOperatorExecutor()

    executor._maybe_emit_loader_slim(runtime, loader_name="demo", result={}, field_keys=["a"])  # noqa: SLF001
    executor._maybe_emit_loader_slim(runtime, loader_name="demo", result={"row1": 1}, field_keys=["a"])  # noqa: SLF001
    executor._maybe_emit_loader_slim(runtime, loader_name="demo", result={"row1": {"a": 1}}, field_keys=["a"])  # noqa: SLF001

    assert instrumentation.loader_slim_calls == []


def test_load_operator_uses_extractor_and_missing_field_spec() -> None:
    loader = _SampleLoader()
    runtime_bindings = RuntimeBindings()

    def _extract(pk, result):  # type: ignore[no-untyped-def]
        row = result[pk]
        return {"amount": row["amount"], "extra": row["extra"]}

    def _params_builder(ctx: LoaderCallContextIr):  # type: ignore[no-untyped-def]
        return (), {"order_ids": list(ctx.batch_row_nth)}

    runtime_bindings.source_loaders["orders"] = loader.get_orders
    runtime_bindings.params_builders[("orders", "order_id")] = _params_builder
    runtime_bindings.loader_extractors["orders"] = _extract
    runtime_bindings.value_transforms["amount"] = lambda value: value * 2  # type: ignore[no-any-return]

    loader_spec = LoaderIr(
        callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders"),
        extractor_ref=RuntimeHandleIdIr(handle_id="loader_extractor:orders"),
        bindings={
            "order_id": BindingIr(
                key_field="order_id",
                params_builder_ref=RuntimeHandleIdIr(handle_id="params_builder:orders:order_id"),
            )
        },
    )
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=loader_spec)
    field_spec = FieldIr(
        field_id="amount",
        name="Amount",
        source_id=source.source_id,
        value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="value_transform:amount")),),
    )

    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount", "extra"])
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(source.source_id): source},
        runtime_bindings=runtime_bindings,
    )
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=str(source.source_id),
        field_keys=("amount", "extra"),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert loader.calls == 1
    assert context.get_field_value("amount", 1) == 20
    assert context.get_field_value("extra", 2) == "y"


def test_execution_runtime_helpers_cover_cache_and_transforms() -> None:
    runtime_bindings = RuntimeBindings()
    key_cast_error = LookupCastSpecIr(name="raise_value_error")
    lookup_cast_error = LookupCastSpecIr(name="raise_type_error")
    key_cast_none = LookupCastSpecIr(name="return_none_key")
    lookup_cast_none = LookupCastSpecIr(name="return_none_lookup")

    runtime_bindings.lookup_key_casts[lookup_cast_id(key_cast_error, is_multi=False)] = _raise_value_error
    runtime_bindings.lookup_key_casts[lookup_cast_id(lookup_cast_error, is_multi=False)] = _raise_type_error
    runtime_bindings.lookup_key_casts[lookup_cast_id(key_cast_none, is_multi=False)] = lambda _value: None  # type: ignore[no-any-return]
    runtime_bindings.lookup_key_casts[lookup_cast_id(lookup_cast_none, is_multi=False)] = lambda _value: None  # type: ignore[no-any-return]

    source = SourceIr(
        source_id="src",
        key=KeyIr(key="id", cast=key_cast_error),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:src")),
    )
    none_transform_source = SourceIr(
        source_id="none",
        key=KeyIr(key="id", cast=key_cast_none),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:none")),
    )
    plain_source = SourceIr(
        source_id="plain",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:plain")),
    )
    plan = ExecutionPlan(field_specs={})
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={
            str(source.source_id): source,
            str(none_transform_source.source_id): none_transform_source,
            str(plain_source.source_id): plain_source,
        },
        runtime_bindings=runtime_bindings,
    )

    assert runtime.get_from_cache("missing", "1") is None
    runtime.preloaded_cache["src"] = {"key": "value"}
    assert runtime.get_from_cache("src", "key") == "value"

    step_with_lookup_error = LookupStepIr(from_field="fk_id", to_source_id=source.source_id, lookup_cast=lookup_cast_error)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_with_lookup_error)
    assert normalized is None
    assert status == "type_error"
    assert message == "bad"

    normalized, status, _ = runtime.normalize_lookup_key_with_status(None, step_with_lookup_error)
    assert normalized is None
    assert status == "null_key"

    step_with_none_cast = LookupStepIr(from_field="fk_id", to_source_id=none_transform_source.source_id)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_with_none_cast)
    assert normalized is None
    assert status == "type_error"
    assert message == "key.cast returned None"

    step_returns_none = LookupStepIr(from_field="fk_id", to_source_id=source.source_id, lookup_cast=lookup_cast_none)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_returns_none)
    assert normalized is None
    assert status == "type_error"
    assert message == "lookup_cast returned None"
    assert runtime.normalize_lookup_key("1", step_returns_none) is None

    plain_step = LookupStepIr(from_field="fk_id", to_source_id=plain_source.source_id)
    normalized, status, _ = runtime.normalize_lookup_key_with_status("ok", plain_step)
    assert normalized == "ok"
    assert status == "ok"
    assert runtime.normalize_lookup_key("ok", plain_step) == "ok"


def test_load_operator_handles_object_data_and_missing_pk() -> None:
    def _loader():  # type: ignore[no-untyped-def]
        return {1: _Order(amount=7)}

    runtime_bindings = RuntimeBindings()
    runtime_bindings.source_loaders["orders"] = _loader
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
    )
    plan = ExecutionPlan(field_specs={}, target_fields=["amount"])
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(source.source_id): source},
        runtime_bindings=runtime_bindings,
    )
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=str(source.source_id),
        field_keys=("amount",),
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) is None


def test_load_operator_rejects_unknown_source_id() -> None:
    plan = ExecutionPlan(field_specs={}, target_fields=())
    runtime = _make_runtime(plan, _make_main_source(), sources={}, runtime_bindings=RuntimeBindings())
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_missing",
        operator_type=OperatorType.LOAD.value,
        source_id="missing",
        field_keys=("amount",),
    )

    with pytest.raises(KeyError, match=r"Unknown source_id"):
        LoadOperatorExecutor().execute(operator, context, [1], runtime)


def test_load_operator_applies_source_normalize_index_by_key() -> None:
    def _loader():  # type: ignore[no-untyped-def]
        return [{"order_id": 1, "amount": 7}, {"order_id": 2, "amount": 9}]

    runtime_bindings = RuntimeBindings()
    runtime_bindings.source_loaders["orders"] = _loader
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="order_id"),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source_id=source.source_id)
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(source.source_id): source},
        runtime_bindings=runtime_bindings,
    )
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=str(source.source_id),
        field_keys=("amount",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) == 9


def test_load_operator_emits_loader_call_skipped_none_rows_for_index_by_key_on_none_skip() -> None:
    class _CaptureLoaderCallHook(BaseHook):
        event_types = {EventType.LOADER_CALL}

        def __init__(self) -> None:
            self.events = []

        def on_event(self, event: Event) -> None:  # type: ignore[override]
            self.events.append(event)

    def _loader():  # type: ignore[no-untyped-def]
        return [
            {"order_id": 1, "amount": 7},
            {"order_id": None, "amount": 0},
            {"order_id": 2, "amount": 9},
        ]

    hook = _CaptureLoaderCallHook()
    runtime_bindings = RuntimeBindings()
    runtime_bindings.source_loaders["orders"] = _loader
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="order_id", on_none="skip"),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source_id=source.source_id)
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(source.source_id): source},
        runtime_bindings=runtime_bindings,
    )
    runtime.instrumentation.register(hook)
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=str(source.source_id),
        field_keys=("amount",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) == 9
    assert hook.events and hook.events[-1].event_type == EventType.LOADER_CALL
    assert hook.events[-1].payload.skipped_none_rows == 1


def test_load_operator_object_missing_attribute_returns_none() -> None:
    class _OrderMissing(object):
        def __init__(self, amount: int) -> None:
            self.amount = amount

    def _loader():  # type: ignore[no-untyped-def]
        return {1: _OrderMissing(amount=7)}

    runtime_bindings = RuntimeBindings()
    runtime_bindings.source_loaders["orders"] = _loader
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
    )
    field_spec = FieldIr(field_id="missing", name="Missing", source_id=source.source_id)
    plan = ExecutionPlan(field_specs={"missing": field_spec}, target_fields=["missing"])
    runtime = _make_runtime(
        plan,
        _make_main_source(),
        sources={str(source.source_id): source},
        runtime_bindings=runtime_bindings,
    )
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source_id=str(source.source_id),
        field_keys=("missing",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("missing", 1) is None


def test_load_operator_execute_returns_early_for_non_load_operator() -> None:
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source_id=source.source_id)
    runtime = _make_runtime(ExecutionPlan(field_specs={"amount": field_spec}), _make_main_source())
    operator = LoadRefOperatorIr(
        operator_id="load_ref_amount",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=str(source.source_id),
        field_key="amount",
        lookup_steps=(),
    )

    LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)


def test_load_operator_executor_ignores_non_load_operator() -> None:
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="source_loader:orders")),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source_id=source.source_id)
    runtime = _make_runtime(ExecutionPlan(field_specs={"amount": field_spec}), _make_main_source())
    context = BatchContext()

    wrong_operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=str(source.source_id),
        field_key="amount",
        lookup_steps=(),
    )

    LoadOperatorExecutor().execute(wrong_operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None
