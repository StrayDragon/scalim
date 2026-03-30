from contextlib import ExitStack
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, List

import pytest

from scalim.events import EVENT_STAGE_SPAN
from scalim.events import Event
from scalim.execution.adaptive.policy import ADAPTIVE_BACKEND_ASYNC, ADAPTIVE_BACKEND_PROCESS, AdaptivePolicy
from scalim.execution.adaptive.policy import ADAPTIVE_BACKEND_THREAD
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.adaptive.tuning import AdaptiveTuning
from scalim.execution.context import BatchContext
from scalim.execution import ScalimEngine
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.base._adaptive_pool import maybe_create_adaptive_pool
from scalim.execution.pipeline.base.pipeline import SeqPipeline
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning import PlanBuilder
from scalim.planning.plan import ExecutionPlan
from scalim.sinks import ISink
from scalim.sinks import InMemoryColumnSink, InMemoryRowSink
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr


def _picklable_test_main_loader() -> List[Dict[str, Any]]:
    return []


def _picklable_test_load_s1() -> Dict[int, Dict[str, Any]]:
    return {1: {"id": 1, "v": "a"}}


def _picklable_test_load_s2() -> Dict[int, Dict[str, Any]]:
    return {2: {"id": 2, "v": "b"}}


class _CollectingSink(ISink):
    def __init__(self) -> None:
        self.rows = []
        self.closed = False

    def write_batch(self, rows) -> None:  # type: ignore[override]
        self.rows.extend(rows)

    def close(self) -> None:
        self.closed = True


def test_pipeline_loads_main_rows_when_missing(
    example_report_ir_module,
    plan_builder,
    engine_factory,
) -> None:
    plan = plan_builder.build(targets=["order_id"])
    engine = engine_factory(plan, batch_size=4)

    results = engine.run()

    expected = example_report_ir_module.data_loader.get_orders(
        "2024-01-01",
        "2024-01-07",
        page=0,
        page_size=10,
    )
    expected_keys = {row["order_id"] for row in expected}

    assert {row["order_id"] for row in results} == expected_keys
    assert engine._pipeline.runtime.preloaded_cache


def test_pipeline_runs_gc_when_interval_hits(plan_builder) -> None:
    plan = plan_builder.build(targets=["order_id"])

    calls = []

    def _fake_collect() -> int:
        calls.append("gc")
        return 0

    overrides = PipelineOverrides(gc_collect_fn=_fake_collect)
    engine = ScalimEngine(
        demand=plan_builder.demand,
        plan=plan,
        batch_size=2,
        gc_interval=1,
        pipeline_overrides=overrides,
    )

    engine.run(main_rows=[{"order_id": 0}, {"order_id": 1}, {"order_id": 2}])

    assert calls


def test_streaming_pipeline_uses_context_when_not_cached(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id", "amount"])
    engine = engine_factory(plan, batch_size=2)
    sink = InMemoryRowSink()

    result = engine.run(main_rows=[{"order_id": 0}, {"order_id": 1}], sink=sink)

    assert result == []
    assert sink.get_data()


def test_parallel_mode_thread_removed(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id"])
    with pytest.raises(ValueError, match="parallel_mode='thread' was removed"):
        _ = engine_factory(plan, parallel_mode="thread", batch_size=2)


def test_parallel_mode_process_removed(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id"])
    with pytest.raises(ValueError, match="parallel_mode='process' was removed"):
        _ = engine_factory(plan, parallel_mode="process", batch_size=2)


def test_scalim_engine_rejects_invalid_batch_size() -> None:
    demand = DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader=_picklable_test_main_loader))
    plan = ExecutionPlan(target_fields=[])

    with pytest.raises(ValueError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=0)

    with pytest.raises(ValueError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=-1)

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=1.5)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size="oops")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=Decimal("2"))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, batch_size=Fraction(4, 2))  # type: ignore[arg-type]


def test_scalim_engine_accepts_none_batch_size_and_runs_single_batch() -> None:
    demand = DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader=_picklable_test_main_loader))
    plan = ExecutionPlan(target_fields=[])

    class _BatchCounterHook(BaseHook):
        def __init__(self) -> None:
            self.pipeline_batch_size = None
            self.batch_start_count = 0

        def on_pipeline_start(self, event) -> None:  # type: ignore[override]
            self.pipeline_batch_size = event.batch_size

        def on_batch_start(self, event) -> None:  # type: ignore[override]
            _ = event
            self.batch_start_count += 1

    hook = _BatchCounterHook()
    manager = HookManager()
    manager.register(hook)

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=None, hook_manager=manager)
    _ = engine.run(main_rows=[{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}])

    assert hook.pipeline_batch_size is None
    assert hook.batch_start_count == 1


def test_adaptive_pipeline_writes_to_batch_sink(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id", "amount"])
    engine = engine_factory(
        plan,
        parallel_mode="adaptive",
        batch_size=2,
        max_workers=2,
    )

    sink = _CollectingSink()
    result = engine.run(main_rows=[{"order_id": 0}, {"order_id": 1}, {"order_id": 2}], sink=sink)

    assert result == []
    assert sink.rows
    assert sink.closed is True


def _make_pipeline(*, overrides: PipelineOverrides) -> SeqPipeline:
    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    demand = DemandIr(sources={}, fields={}, main_source=main_source)
    plan = ExecutionPlan(target_fields=[])
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, main_source=main_source, parallel_mode="adaptive", max_workers=2)
    executor = BatchExecutor(plan, runtime, overrides=overrides)
    return SeqPipeline(plan, executor, runtime, hook_manager, observer_manager, demand, batch_size=10, overrides=overrides)


def test_maybe_create_adaptive_pool_returns_none_when_workers_le_1() -> None:
    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    plan = ExecutionPlan(target_fields=[])
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(
        plan,
        hook_manager,
        observer_manager,
        main_source=main_source,
        parallel_mode="adaptive",
        max_workers=1,
    )

    overrides = PipelineOverrides()
    with ExitStack() as stack:
        pool = maybe_create_adaptive_pool(
            plan=plan,
            runtime=runtime,
            overrides=overrides,
            stack=stack,
            sys_module=object(),
            warnings_module=object(),
        )

    assert pool is None


@pytest.mark.parametrize("backend", [ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_ASYNC])
def test_maybe_create_adaptive_pool_rejects_pruned_backend(backend: str) -> None:
    class _PrunedBackendPolicy(AdaptivePolicy):
        def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
            _ = plan
            _ = runtime
            _ = tuning
            return backend

    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    plan = ExecutionPlan(target_fields=[])
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=main_source,
        parallel_mode="adaptive",
        max_workers=2,
    )
    overrides = PipelineOverrides(adaptive_policy=_PrunedBackendPolicy(), adaptive_tuning=AdaptiveTuning(max_workers=2))

    with ExitStack() as stack:
        with pytest.raises(ValueError) as excinfo:
            maybe_create_adaptive_pool(
                plan=plan,
                runtime=runtime,
                overrides=overrides,
                stack=stack,
                sys_module=object(),
                warnings_module=object(),
            )

    msg = str(excinfo.value)
    assert "暂不支持" in msg
    assert "当前仅支持 thread" in msg
    assert "backend 改为 'thread'" in msg


def test_adaptive_scheduler_rejects_invalid_backend() -> None:
    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_picklable_test_load_s1))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=s1,
        field_key="a",
        field_spec=FieldIr(field_id="a", name="a", source=s1),
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    plan = ExecutionPlan(operators=(op_a,), field_specs={"a": op_a.field_spec})
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader=_picklable_test_main_loader),
        parallel_mode="adaptive",
        max_workers=2,
    )
    runtime.adaptive_backend = "nope"

    overrides = PipelineOverrides(adaptive_tuning=AdaptiveTuning(max_workers=2))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)

    ctx = BatchContext()
    ctx.set_field_value("fk1", 0, 1)

    with pytest.raises(ValueError, match="Invalid adaptive backend"):
        scheduler.execute_segment(
            [op_a],
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            pool=None,
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )


@pytest.mark.parametrize("backend", [ADAPTIVE_BACKEND_PROCESS, ADAPTIVE_BACKEND_ASYNC])
def test_adaptive_scheduler_rejects_pruned_backend_selected_in_runtime(backend: str) -> None:
    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_picklable_test_load_s1))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=s1,
        field_key="a",
        field_spec=FieldIr(field_id="a", name="a", source=s1),
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    plan = ExecutionPlan(operators=(op_a,), field_specs={"a": op_a.field_spec})
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader=_picklable_test_main_loader),
        parallel_mode="adaptive",
        max_workers=2,
    )
    runtime.adaptive_backend = backend

    overrides = PipelineOverrides(adaptive_tuning=AdaptiveTuning(max_workers=2))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)

    ctx = BatchContext()
    ctx.set_field_value("fk1", 0, 1)

    with pytest.raises(ValueError) as excinfo:
        scheduler.execute_segment(
            [op_a],
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            pool=None,
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )

    msg = str(excinfo.value)
    assert "暂不支持" in msg
    assert "当前仅支持 thread" in msg
    assert "backend 改为 'thread'" in msg


def test_adaptive_scheduler_uses_runtime_backend_selected_by_pool() -> None:
    class _TogglingPolicy(AdaptivePolicy):
        def __init__(self) -> None:
            self.calls = 0

        def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
            _ = plan
            _ = runtime
            _ = tuning
            self.calls += 1
            return ADAPTIVE_BACKEND_THREAD if self.calls == 1 else ADAPTIVE_BACKEND_PROCESS

    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_picklable_test_load_s1))
    s2 = SourceIr(source_id="s2", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_picklable_test_load_s2))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source=s1,
        field_key="a",
        field_spec=FieldIr(field_id="a", name="a", source=s1),
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    op_b = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type=OperatorType.LOAD_REF.value,
        source=s2,
        field_key="b",
        field_spec=FieldIr(field_id="b", name="b", source=s2),
        lookup_steps=(LookupStepIr(from_field="fk2", to_source=s2),),
    )

    plan = ExecutionPlan(operators=(op_a, op_b), field_specs={"a": op_a.field_spec, "b": op_b.field_spec})
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader=_picklable_test_main_loader),
        parallel_mode="adaptive",
        max_workers=2,
    )

    policy = _TogglingPolicy()
    overrides = PipelineOverrides(
        adaptive_policy=policy,
        adaptive_tuning=AdaptiveTuning(max_workers=2),
    )

    with ExitStack() as stack:
        pool = maybe_create_adaptive_pool(
            plan=plan,
            runtime=runtime,
            overrides=overrides,
            stack=stack,
            sys_module=object(),
            warnings_module=object(),
        )
        assert pool is not None

        ctx = BatchContext()
        ctx.set_field_value("fk1", 0, 1)
        ctx.set_field_value("fk2", 0, 2)

        scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)
        scheduler.execute_segment(
            [op_a, op_b],
            context=ctx,
            batch_row_nth=[0],
            runtime=runtime,
            pool=pool,
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )

    assert policy.calls == 1


def test_load_ref_flow_null_fill_row_is_noop_when_empty() -> None:
    from scalim.execution.executor.operators.load_ref import flow as flow_module  # noqa: PLC0415

    flow_module._null_fill_row(exec_ctx=object(), row_id=0, null_fill_fields=())  # type: ignore[arg-type]


def test_seq_pipeline_adaptive_invalid_backend_raises() -> None:
    class _BadPolicy(AdaptivePolicy):
        def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
            _ = plan
            _ = runtime
            _ = tuning
            return "bad"

    overrides = PipelineOverrides(
        adaptive_policy=_BadPolicy(),
        adaptive_tuning=AdaptiveTuning(max_workers=2),
    )
    pipeline = _make_pipeline(overrides=overrides)
    with pytest.raises(ValueError, match="Invalid adaptive backend"):
        _ = pipeline.run(main_rows=[])


class _StageSpanHook(BaseHook):
    event_types = {EVENT_STAGE_SPAN}

    def __init__(self) -> None:
        self.events: List[Event] = []

    def on_event(self, event: Event) -> None:  # type: ignore[override]
        self.events.append(event)


def _make_simple_demand_and_plan():
    def _load_orders() -> List[Dict[str, Any]]:
        return [
            {"order_id": 0, "customer_id": 100},
            {"order_id": 1, "customer_id": 101},
        ]

    def _load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        _ = customer_id_set
        return {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
        }

    def _build_keys_params(field_name: str, param_name: str):  # type: ignore[no-untyped-def]
        def _builder(ctx):  # type: ignore[no-untyped-def]
            return (), {param_name: set(ctx.lookup_keys or set())}

        return BindingIr(key_field=field_name, params_builder=_builder, mode="keys")

    orders = MainSourceIr(source_id="orders", loader=_load_orders)
    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=_load_customers,
            bindings={"customer_id": _build_keys_params("customer_id", "customer_id_set")},
        ),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders, is_primary=True),
        FieldIr(
            field_id="customer_name",
            name="客户",
            source=customers,
            data_key="customer_name",
            relation=orders["customer_id"].join(customers["customer_id"]),
        ),
    ]
    demand = DemandIr.from_irs(sources=[customers], fields=fields, main_source=orders)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])
    return demand, plan, _load_orders


@pytest.mark.parametrize("sink_mode", ["memory", "column"], ids=["memory", "column"])
def test_stage_spans_emitted(sink_mode: str) -> None:
    demand, plan, load_orders = _make_simple_demand_and_plan()
    hook = _StageSpanHook()
    hooks = HookManager()
    hooks.register(hook)

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=10, parallel_mode="seq", hook_manager=hooks)
    if sink_mode == "column":
        with InMemoryColumnSink(field_names=plan.target_fields) as sink:
            _ = engine.run(main_rows=list(load_orders()), sink=sink)
    else:
        _ = engine.run(main_rows=list(load_orders()))

    assert hook.events
    assert all(e.event_type == EVENT_STAGE_SPAN for e in hook.events)
