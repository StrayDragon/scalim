"""Executor operator tests: load."""

from scalim.execution.context import BatchContext
from scalim.events import EVENT_LOADER_CALL, EVENT_LOADER_SLIM, Event
from scalim.execution.executor.operators.load import LoadOperatorExecutor
from scalim.planning.operators import LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, SourceIr, SourceNormalizeIr
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
    binding = BindingIr(key_field="k", params_builder=lambda ctx: ((), {"src": ctx.source_id}))
    loader_context = LoaderCallContextIr(source_id="main")
    runtime = _Runtime(_WantsInstrumentation(EVENT_LOADER_CALL))

    executor = LoadOperatorExecutor()
    assert executor._build_loader_call_kwargs(runtime, binding, loader_context) == {"src": "main"}  # noqa: SLF001


def test_load_operator_maybe_emit_loader_slim_extracts_key_count() -> None:
    instrumentation = _WantsInstrumentation(EVENT_LOADER_SLIM)
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


def test_load_operator_uses_extractor_and_missing_field_spec() -> None:
    loader = _SampleLoader()

    def _extract(pk, result):  # type: ignore[no-untyped-def]
        row = result[pk]
        return {"amount": row["amount"], "extra": row["extra"]}

    loader_spec = LoaderIr(
        callable=loader.get_orders,
        extractor=_extract,
        bindings={
            "order_id": BindingIr(
                key_field="order_id",
                params_builder=lambda ctx: ((), {"order_ids": list(ctx.batch_row_nth)}),
            )
        },
    )
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=loader_spec)
    field_spec = FieldIr(field_id="amount", name="Amount", source=source, transform=lambda value: value * 2)

    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount", "extra"])
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount", "extra"),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert loader.calls == 1
    assert context.get_field_value("amount", 1) == 20
    assert context.get_field_value("extra", 2) == "y"


def test_execution_runtime_helpers_cover_cache_and_transforms() -> None:
    source = SourceIr(
        source_id="src",
        key=KeyIr(key="id", cast=_raise_value_error),
        loader_spec=LoaderIr(callable=lambda: {}),
    )
    plan = ExecutionPlan(field_specs={})
    runtime = _make_runtime(plan, _make_main_source())

    assert runtime.get_from_cache("missing", "1") is None
    runtime.preloaded_cache["src"] = {"key": "value"}
    assert runtime.get_from_cache("src", "key") == "value"

    step_with_lookup_error = LookupStepIr(from_field="fk_id", to_source=source, lookup_cast=_raise_type_error)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_with_lookup_error)
    assert normalized is None
    assert status == "type_error"
    assert message == "bad"

    normalized, status, _ = runtime.normalize_lookup_key_with_status(None, step_with_lookup_error)
    assert normalized is None
    assert status == "null_key"

    none_transform_source = SourceIr(
        source_id="none",
        key=KeyIr(key="id", cast=lambda _value: None),
        loader_spec=LoaderIr(callable=lambda: {}),
    )
    step_with_none_cast = LookupStepIr(from_field="fk_id", to_source=none_transform_source)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_with_none_cast)
    assert normalized is None
    assert status == "type_error"
    assert message == "key.cast returned None"

    step_returns_none = LookupStepIr(from_field="fk_id", to_source=source, lookup_cast=lambda _value: None)
    normalized, status, message = runtime.normalize_lookup_key_with_status("1", step_returns_none)
    assert normalized is None
    assert status == "type_error"
    assert message == "lookup_cast returned None"
    assert runtime.normalize_lookup_key("1", step_returns_none) is None

    plain_source = SourceIr(source_id="plain", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    plain_step = LookupStepIr(from_field="fk_id", to_source=plain_source)
    normalized, status, _ = runtime.normalize_lookup_key_with_status("ok", plain_step)
    assert normalized == "ok"
    assert status == "ok"
    assert runtime.normalize_lookup_key("ok", plain_step) == "ok"


def test_load_operator_handles_object_data_and_missing_pk() -> None:
    def _loader():  # type: ignore[no-untyped-def]
        return {1: _Order(amount=7)}

    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=_loader))
    plan = ExecutionPlan(field_specs={}, target_fields=["amount"])
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount",),
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) is None


def test_load_operator_applies_source_normalize_index_by_key() -> None:
    def _loader():  # type: ignore[no-untyped-def]
        return [{"order_id": 1, "amount": 7}, {"order_id": 2, "amount": 9}]

    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable=_loader),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="order_id"),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) == 9


def test_load_operator_emits_loader_call_skipped_none_rows_for_index_by_key_on_none_skip() -> None:
    class _CaptureLoaderCallHook(BaseHook):
        event_types = {EVENT_LOADER_CALL}

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
    source = SourceIr(
        source_id="orders",
        key=KeyIr(key="order_id"),
        loader_spec=LoaderIr(callable=_loader),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="order_id", on_none="skip"),
    )
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    plan = ExecutionPlan(field_specs={"amount": field_spec}, target_fields=["amount"])
    runtime = _make_runtime(plan, _make_main_source())
    runtime.instrumentation.register(hook)
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("amount",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1, 2], runtime)

    assert context.get_field_value("amount", 1) == 7
    assert context.get_field_value("amount", 2) == 9
    assert hook.events and hook.events[-1].event_type == EVENT_LOADER_CALL
    assert hook.events[-1].payload.skipped_none_rows == 1


def test_load_operator_object_missing_attribute_returns_none() -> None:
    class _OrderMissing(object):
        def __init__(self, amount: int) -> None:
            self.amount = amount

    def _loader():  # type: ignore[no-untyped-def]
        return {1: _OrderMissing(amount=7)}

    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=_loader))
    field_spec = FieldIr(field_id="missing", name="Missing", source=source)
    plan = ExecutionPlan(field_specs={"missing": field_spec}, target_fields=["missing"])
    runtime = _make_runtime(plan, _make_main_source())
    context = BatchContext()

    operator = LoadOperatorIr(
        operator_id="load_orders",
        operator_type=OperatorType.LOAD.value,
        source=source,
        field_keys=("missing",),
        is_primary=True,
    )

    LoadOperatorExecutor().execute(operator, context, [1], runtime)

    assert context.get_field_value("missing", 1) is None


def test_load_operator_execute_returns_early_for_non_load_operator() -> None:
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    runtime = _make_runtime(ExecutionPlan(field_specs={"amount": field_spec}), _make_main_source())
    operator = LoadRefOperatorIr(
        operator_id="load_ref_amount",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_spec,
        lookup_steps=(),
    )

    LoadOperatorExecutor().execute(operator, BatchContext(), [1], runtime)


def test_load_operator_executor_ignores_non_load_operator() -> None:
    source = SourceIr(source_id="orders", key=KeyIr(key="order_id"), loader_spec=LoaderIr(callable=lambda: {}))
    field_spec = FieldIr(field_id="amount", name="Amount", source=source)
    runtime = _make_runtime(ExecutionPlan(field_specs={"amount": field_spec}), _make_main_source())
    context = BatchContext()

    wrong_operator = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_spec,
        lookup_steps=(),
    )

    LoadOperatorExecutor().execute(wrong_operator, context, [1], runtime)
    assert context.get_field_value("amount", 1) is None
