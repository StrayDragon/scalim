import logging
from typing import Any, Dict, List, Optional

from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.events.events import LoaderCallEvent
from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.logs import LoggingObserver
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


class _LoaderEventCapture(BaseHook):
    def __init__(self) -> None:
        self.events: List[LoaderCallEvent] = []

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        self.events.append(event)


def _make_main_source(source_id: str = "orders") -> MainSourceIr:
    return MainSourceIr(source_id=source_id, loader=lambda: [])


class _SampleLoader(object):
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, order_ids):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {oid: {"amount": oid * 10, "extra": "x{}".format(oid)} for oid in order_ids}


class _RowsLoader(object):
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, rows):  # type: ignore[no-untyped-def]
        self.calls += 1
        result: Dict[int, Dict[str, Any]] = {}
        for row in rows or []:
            order_id = row.get("order_id")
            if order_id is None:
                continue
            result[int(order_id)] = {"name": "n{}".format(order_id), "level": "l{}".format(order_id)}
        return result


def _make_rows_binding(cache_mode: str) -> BindingIr:
    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        return (), {"rows": list(ctx.batch_rows or [])}

    return BindingIr(
        key_field="order_id",
        params_builder=_params_builder,
        mode="rows",
        as_="set",
        cache_mode=cache_mode,
        param_name="rows",
    )


def _make_runtime_with_ops(
    operators: List[LoadRefOperatorIr],
    field_specs: Dict[str, FieldIr],
    hook_manager: HookManager,
    observer_manager: Optional[ObserverManager] = None,
) -> ExecutionRuntime:
    plan = ExecutionPlan(operators=tuple(operators), field_specs=field_specs)
    observer_manager = observer_manager or ObserverManager()
    return ExecutionRuntime(plan, hook_manager, observer_manager, main_source=_make_main_source())


def test_loadref_reuse_and_group_field_keys() -> None:
    loader = _SampleLoader()
    field_keys_seen: List[tuple] = []

    def _params_builder(ctx):  # type: ignore[no-untyped-def]
        field_keys_seen.append(tuple(ctx.field_keys))
        return (), {"order_ids": list(ctx.lookup_keys or [])}

    binding = BindingIr(key_field="order_id", params_builder=_params_builder)
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
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

    hook_manager = HookManager()
    runtime = _make_runtime_with_ops([op_amount, op_extra], {"amount": field_amount, "extra": field_extra}, hook_manager)
    runtime.batch_num = 1
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_amount, context, [1, 2], runtime)
    executor.execute(op_extra, context, [1, 2], runtime)

    assert loader.calls == 1
    assert context.get_field_value("amount", 1) == 10
    assert context.get_field_value("extra", 2) == "x2"
    assert field_keys_seen
    assert set(field_keys_seen[0]) == {"amount", "extra"}


def test_loadref_cache_status_events() -> None:
    loader = _SampleLoader()

    binding = BindingIr(key_field="order_id", params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys or [])}))
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
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

    capture = _LoaderEventCapture()
    hook_manager = HookManager()
    hook_manager.register(capture)
    runtime = _make_runtime_with_ops([op_amount, op_extra], {"amount": field_amount, "extra": field_extra}, hook_manager)
    runtime.batch_num = 3
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_amount, context, [1, 2], runtime)
    executor.execute(op_extra, context, [1, 2], runtime)

    assert len(capture.events) == 1
    assert capture.events[0].cache_status == "miss"
    assert capture.events[0].batch_num == 3
    assert capture.events[0].lookup_key_count == 2
    assert set(capture.events[0].field_keys or []) == {"amount", "extra"}


def test_loadref_no_reuse_for_different_relation_signature() -> None:
    loader = _SampleLoader()
    binding = BindingIr(key_field="order_id", params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys or [])}))
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    def _cast_a(value):  # type: ignore[no-untyped-def]
        return value

    def _cast_b(value):  # type: ignore[no-untyped-def]
        return value

    step_a = LookupStepIr(from_field="order_id", to_source=source, lookup_cast=_cast_a)
    step_b = LookupStepIr(from_field="order_id", to_source=source, lookup_cast=_cast_b)
    field_a = FieldIr(field_id="amount", name="Amount", source=source, lookup_steps=(step_a,))
    field_b = FieldIr(field_id="extra", name="Extra", source=source, lookup_steps=(step_b,))

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_a,
        lookup_steps=(step_a,),
    )
    op_b = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="extra",
        field_spec=field_b,
        lookup_steps=(step_b,),
    )

    hook_manager = HookManager()
    runtime = _make_runtime_with_ops([op_a, op_b], {"amount": field_a, "extra": field_b}, hook_manager)
    runtime.batch_num = 1
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_a, context, [1, 2], runtime)
    executor.execute(op_b, context, [1, 2], runtime)

    assert loader.calls == 2


def test_loadref_skip_repeated_execution_for_same_relation_group() -> None:
    loader = _SampleLoader()
    binding = BindingIr(key_field="order_id", params_builder=lambda ctx: ((), {"order_ids": list(ctx.lookup_keys or [])}))
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="payments", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
    field_amount = FieldIr(field_id="amount", name="Amount", source=source, lookup_steps=(step,))
    op_amount = LoadRefOperatorIr(
        operator_id="load_ref_0",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="amount",
        field_spec=field_amount,
        lookup_steps=(step,),
    )

    hook_manager = HookManager()
    runtime = _make_runtime_with_ops([op_amount], {"amount": field_amount}, hook_manager)
    runtime.batch_num = 1
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)
    context.set_field_value("order_id", 3, 3)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_amount, context, [1, 2], runtime)
    executor.execute(op_amount, context, [3], runtime)

    assert loader.calls == 1


def test_logging_hook_outputs_cache_status(caplog) -> None:
    logger = logging.getLogger("scalim.tests.loader_cache")
    hook = LoggingObserver(logger=logger)
    event = LoaderCallEvent(
        loader_name="demo_loader",
        params={},
        result={1: {"x": 1}},
        duration=0.1,
        cache_status="hit",
        field_keys=["amount", "extra"],
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        hook.on_loader_call(event)

    messages = [record.getMessage() for record in caplog.records]
    assert any("cache_status=hit" in message for message in messages)
    assert any("cache_fields=amount,extra" in message for message in messages)


def test_rows_loadref_default_batch_reuse() -> None:
    loader = _RowsLoader()
    binding = _make_rows_binding(cache_mode="batch")
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="customers", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
    field_name = FieldIr(field_id="name", name="Name", source=source, lookup_steps=(step,))
    field_level = FieldIr(field_id="level", name="Level", source=source, lookup_steps=(step,))

    op_name = LoadRefOperatorIr(
        operator_id="load_ref_name",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="name",
        field_spec=field_name,
        lookup_steps=(step,),
    )
    op_level = LoadRefOperatorIr(
        operator_id="load_ref_level",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="level",
        field_spec=field_level,
        lookup_steps=(step,),
    )

    hook_manager = HookManager()
    runtime = _make_runtime_with_ops([op_name, op_level], {"name": field_name, "level": field_level}, hook_manager)
    runtime.batch_num = 1
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_name, context, [1, 2], runtime)
    executor.execute(op_level, context, [1, 2], runtime)

    assert loader.calls == 1
    assert context.get_field_value("name", 1) == "n1"
    assert context.get_field_value("level", 2) == "l2"


def test_rows_loadref_cache_mode_none_disables_reuse() -> None:
    loader = _RowsLoader()
    binding = _make_rows_binding(cache_mode="none")
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="customers", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
    field_name = FieldIr(field_id="name", name="Name", source=source, lookup_steps=(step,))
    field_level = FieldIr(field_id="level", name="Level", source=source, lookup_steps=(step,))

    op_name = LoadRefOperatorIr(
        operator_id="load_ref_name",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="name",
        field_spec=field_name,
        lookup_steps=(step,),
    )
    op_level = LoadRefOperatorIr(
        operator_id="load_ref_level",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="level",
        field_spec=field_level,
        lookup_steps=(step,),
    )

    hook_manager = HookManager()
    runtime = _make_runtime_with_ops([op_name, op_level], {"name": field_name, "level": field_level}, hook_manager)
    runtime.batch_num = 2
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_name, context, [1, 2], runtime)
    executor.execute(op_level, context, [1, 2], runtime)

    assert loader.calls == 2


def test_rows_loadref_cache_uses_first_batch_rows_snapshot() -> None:
    loader = _RowsLoader()
    binding = _make_rows_binding(cache_mode="batch")
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="customers", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
    field_name = FieldIr(field_id="name", name="Name", source=source, lookup_steps=(step,))
    field_level = FieldIr(field_id="level", name="Level", source=source, lookup_steps=(step,))

    op_name = LoadRefOperatorIr(
        operator_id="load_ref_name",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="name",
        field_spec=field_name,
        lookup_steps=(step,),
    )
    op_level = LoadRefOperatorIr(
        operator_id="load_ref_level",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="level",
        field_spec=field_level,
        lookup_steps=(step,),
    )

    capture = _LoaderEventCapture()
    hook_manager = HookManager()
    hook_manager.register(capture)
    runtime = _make_runtime_with_ops([op_name, op_level], {"name": field_name, "level": field_level}, hook_manager)
    runtime.batch_num = 5
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_name, context, [1, 2], runtime)
    assert context.has_field("name")
    executor.execute(op_level, context, [1, 2], runtime)

    assert len(capture.events) == 1
    first_rows = capture.events[0].params.get("rows")
    assert first_rows is not None
    assert all("name" not in row for row in first_rows)
    assert all("level" not in row for row in first_rows)
    assert capture.events[0].cache_status == "miss"


def test_loadref_cached_rows_hit_reuses_cached_batch_rows() -> None:
    loader = _RowsLoader()
    binding = _make_rows_binding(cache_mode="batch")
    loader_spec = LoaderIr(callable=loader, bindings={"order_id": binding})
    source = SourceIr(source_id="customers", key=KeyIr(key="order_id"), loader_spec=loader_spec)

    step = LookupStepIr(from_field="order_id", to_source=source)
    field_name = FieldIr(field_id="name", name="Name", source=source, lookup_steps=(step,))

    op_name = LoadRefOperatorIr(
        operator_id="load_ref_name",
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key="name",
        field_spec=field_name,
        lookup_steps=(step,),
    )

    capture = _LoaderEventCapture()
    hook_manager = HookManager()
    hook_manager.register(capture)
    runtime = _make_runtime_with_ops([op_name], {"name": field_name}, hook_manager)
    runtime.batch_num = 6
    context = BatchContext()
    context.set_field_value("order_id", 1, 1)
    context.set_field_value("order_id", 2, 2)

    executor = LoadRefOperatorExecutor()
    executor.execute(op_name, context, [1, 2], runtime)

    context.set_field_value("note", 1, "n1")

    runtime.load_ref_group_executed.clear()
    executor.execute(op_name, context, [1, 2], runtime)

    assert loader.calls == 1
    assert len(capture.events) == 2
    assert capture.events[0].cache_status == "miss"
    assert capture.events[1].cache_status == "hit"
