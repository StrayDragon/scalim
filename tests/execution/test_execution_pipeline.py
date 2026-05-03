from contextlib import ExitStack
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, List

import pytest

from scalim.events import Event, EventType
from scalim.execution.adaptive.policy import ADAPTIVE_BACKEND_ASYNC, ADAPTIVE_BACKEND_PROCESS, AdaptivePolicy
from scalim.execution.adaptive.policy import ADAPTIVE_BACKEND_THREAD
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.adaptive.tuning import AdaptiveTuning
from scalim.execution.context import BatchContext
from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
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
from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
from scalim.spec.ir import BindingIr, DemandIr, FieldIr, KeyIr, LoaderIr, LookupStepIr, MainSourceIr, RuntimeHandleIdIr, SourceIr


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


def test_pipeline_runs_gc_when_interval_hits(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id"])

    calls = []

    def _fake_collect() -> int:
        calls.append("gc")
        return 0

    overrides = PipelineOverrides(gc_collect_fn=_fake_collect)
    engine = engine_factory(plan, batch_size=2, gc_interval=1, pipeline_overrides=overrides)

    engine.run(main_rows=[{"order_id": 0}, {"order_id": 1}, {"order_id": 2}])

    assert calls


def test_pipeline_consume_clears_internal_main_rows_list() -> None:
    captured = {"rows": None}

    def _main_loader() -> List[Dict[str, Any]]:
        rows = [{"order_id": i} for i in range(5)]
        captured["rows"] = rows
        return rows

    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    demand = DemandIr(
        sources={},
        fields={"order_id": FieldIr(field_id="order_id", name="order_id", source=main_source, is_primary=True)},
        main_source=main_source,
    )
    plan = PlanBuilder(demand).build(targets=["order_id"])
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": _main_loader})

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=2)
    results = engine.run()

    assert [row["order_id"] for row in results] == [0, 1, 2, 3, 4]

    loaded = captured["rows"]
    assert isinstance(loaded, list)
    assert loaded == [{}, {}, {}, {}, {}]


def test_pipeline_consume_clear_helper_guard_clauses() -> None:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    demand = DemandIr(
        sources={},
        fields={"order_id": FieldIr(field_id="order_id", name="order_id", source=main_source, is_primary=True)},
        main_source=main_source,
    )
    plan = PlanBuilder(demand).build(targets=["order_id"])
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": (lambda: [])})

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=2)
    pipeline = engine._pipeline
    assert isinstance(pipeline, SeqPipeline)

    rows: List[Dict[str, Any]] = [{"order_id": 0}, {"order_id": 1}]
    batch_rows: List[Dict[str, Any]] = [rows[0]]

    pipeline._maybe_consume_clear_main_rows_list(enabled=False, main_rows=rows, row_ids=[0], batch_rows=batch_rows)
    pipeline._maybe_consume_clear_main_rows_list(enabled=True, main_rows=rows, row_ids=[], batch_rows=batch_rows)
    pipeline._maybe_consume_clear_main_rows_list(  # type: ignore[list-item]
        enabled=True,
        main_rows=rows,
        row_ids=["x"],
        batch_rows=batch_rows,
    )
    pipeline._maybe_consume_clear_main_rows_list(enabled=True, main_rows=iter(rows), row_ids=[0], batch_rows=batch_rows)
    pipeline._maybe_consume_clear_main_rows_list(enabled=True, main_rows=rows, row_ids=[0], batch_rows=[])
    pipeline._maybe_consume_clear_main_rows_list(enabled=True, main_rows=rows, row_ids=[-1], batch_rows=batch_rows)
    pipeline._maybe_consume_clear_main_rows_list(
        enabled=True,
        main_rows=rows,
        row_ids=[1],
        batch_rows=[rows[0], rows[1], {"order_id": 2}],
    )

    assert rows[0].get("order_id") == 0
    assert rows[1].get("order_id") == 1

    pipeline._maybe_consume_clear_main_rows_list(enabled=True, main_rows=rows, row_ids=[0], batch_rows=rows)
    assert rows == [{}, {}]


def test_streaming_pipeline_uses_context_when_not_cached(plan_builder, engine_factory) -> None:
    plan = plan_builder.build(targets=["order_id", "amount"])
    engine = engine_factory(plan, batch_size=2)
    sink = InMemoryRowDataSink()

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
    demand = DemandIr(
        sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    )
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": _picklable_test_main_loader})
    plan = ExecutionPlan(target_fields=[])

    with pytest.raises(ValueError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=0)

    with pytest.raises(ValueError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=-1)

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=True)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1.5)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size="oops")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=Decimal("2"))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="batch_size"):
        _ = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=Fraction(4, 2))  # type: ignore[arg-type]


def test_scalim_engine_accepts_none_batch_size_and_runs_single_batch() -> None:
    demand = DemandIr(
        sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    )
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": _picklable_test_main_loader})
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

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=None, hook_manager=manager)
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
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": lambda: []})
    demand = DemandIr(sources={}, fields={}, main_source=main_source)
    plan = ExecutionPlan(target_fields=[])
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(
        plan,
        hook_manager,
        observer_manager,
        main_source=main_source,
        sources=demand.sources,
        runtime_bindings=runtime_bindings,
        parallel_mode="adaptive",
        max_workers=2,
    )
    executor = BatchExecutor(plan, runtime, overrides=overrides)
    return SeqPipeline(plan, executor, runtime, hook_manager, observer_manager, demand, batch_size=10, overrides=overrides)


def test_maybe_create_adaptive_pool_returns_none_when_workers_le_1() -> None:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    plan = ExecutionPlan(target_fields=[])
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": lambda: []})
    runtime = ExecutionRuntime(
        plan,
        hook_manager,
        observer_manager,
        main_source=main_source,
        sources={},
        runtime_bindings=runtime_bindings,
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

    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    plan = ExecutionPlan(target_fields=[])
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": lambda: []})
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=main_source,
        sources={},
        runtime_bindings=runtime_bindings,
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
    assert "not supported" in msg
    assert "'thread'" in msg


def test_adaptive_scheduler_rejects_invalid_backend() -> None:
    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=s1.source_id,
        field_key="a",
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    field_spec = FieldIr(field_id="a", name="a", source=s1)
    plan = ExecutionPlan(operators=(op_a,), field_specs={"a": field_spec}, ref_loader_sequence=[(s1, [("a", ())])])
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": _picklable_test_main_loader}, source_loaders={"s1": _picklable_test_load_s1}
    )
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources={"s1": s1},
        runtime_bindings=runtime_bindings,
        parallel_mode="adaptive",
        max_workers=2,
    )
    runtime.adaptive_backend = "nope"

    overrides = PipelineOverrides(adaptive_tuning=AdaptiveTuning(max_workers=2))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)

    ctx = BatchContext()
    ctx.set_field_value("fk1", 0, 1)

    with pytest.raises(ValueError, match="not supported"):
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
    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=s1.source_id,
        field_key="a",
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    field_spec = FieldIr(field_id="a", name="a", source=s1)
    plan = ExecutionPlan(operators=(op_a,), field_specs={"a": field_spec}, ref_loader_sequence=[(s1, [("a", ())])])
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": _picklable_test_main_loader}, source_loaders={"s1": _picklable_test_load_s1}
    )
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources={"s1": s1},
        runtime_bindings=runtime_bindings,
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
    assert "not supported" in msg
    assert "'thread'" in msg


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

    s1 = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")))
    s2 = SourceIr(source_id="s2", key=KeyIr(key="id"), loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s2.loader")))

    from scalim.planning.operators import LoadRefOperatorIr, OperatorType  # noqa: PLC0415

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=s1.source_id,
        field_key="a",
        lookup_steps=(LookupStepIr(from_field="fk1", to_source=s1),),
    )
    op_b = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=s2.source_id,
        field_key="b",
        lookup_steps=(LookupStepIr(from_field="fk2", to_source=s2),),
    )

    field_a = FieldIr(field_id="a", name="a", source=s1)
    field_b = FieldIr(field_id="b", name="b", source=s2)
    plan = ExecutionPlan(
        operators=(op_a, op_b),
        field_specs={"a": field_a, "b": field_b},
        ref_loader_sequence=[(s1, [("a", ())]), (s2, [("b", ())])],
    )
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": _picklable_test_main_loader},
        source_loaders={"s1": _picklable_test_load_s1, "s2": _picklable_test_load_s2},
    )
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources={"s1": s1, "s2": s2},
        runtime_bindings=runtime_bindings,
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
    with pytest.raises(ValueError, match="not supported"):
        _ = pipeline.run(main_rows=[])


class _StageSpanHook(BaseHook):
    event_types = {EventType.STAGE_SPAN}

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

    def _build_keys_params(field_name: str, param_name: str) -> BindingIr:
        return BindingIr(
            key_field=field_name,
            params_builder_ref=RuntimeHandleIdIr(handle_id="customers.params_builder.{}".format(field_name)),
            param_name=param_name,
            mode="keys",
        )

    orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="customers.loader"),
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
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": _load_orders},
        source_loaders={"customers": _load_customers},
        params_builders={
            ("customers", "customer_id"): (lambda ctx: ((), {"customer_id_set": set(ctx.lookup_keys or set())})),
        },
    )
    return demand, plan, runtime_bindings, _load_orders


@pytest.mark.parametrize("sink_mode", ["memory", "column"], ids=["memory", "column"])
def test_stage_spans_emitted(sink_mode: str) -> None:
    demand, plan, runtime_bindings, load_orders = _make_simple_demand_and_plan()
    hook = _StageSpanHook()
    hooks = HookManager()
    hooks.register(hook)

    engine = ScalimEngine(
        demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=10, parallel_mode="seq", hook_manager=hooks
    )
    if sink_mode == "column":
        with InMemoryColumnSink(field_names=plan.target_fields) as sink:
            _ = engine.run(main_rows=list(load_orders()), sink=sink)
    else:
        _ = engine.run(main_rows=list(load_orders()))

    assert hook.events
    assert all(e.event_type == EventType.STAGE_SPAN for e in hook.events)
