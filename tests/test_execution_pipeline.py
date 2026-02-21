import gc
from contextlib import ExitStack
from typing import Any, Dict, List

import pytest

from scalim.events.catalog import EVENT_STAGE_SPAN
from scalim.events.event import Event
from scalim.execution.adaptive.policy import ADAPTIVE_BACKEND_ASYNC, ADAPTIVE_BACKEND_PROCESS, AdaptivePolicy
from scalim.execution.adaptive.tuning import AdaptiveTuning
from scalim.execution.engine import ScalimEngine
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.base._adaptive_pool import maybe_create_adaptive_pool
from scalim.execution.pipeline.base.pipeline import SeqPipeline
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.builder import PlanBuilder
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.sink_base import ISink
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


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


def test_pipeline_runs_gc_when_interval_hits(plan_builder, engine_factory, monkeypatch) -> None:
    plan = plan_builder.build(targets=["order_id"])
    engine = engine_factory(plan, batch_size=2, gc_interval=1)

    calls = []

    def _fake_collect() -> int:
        calls.append("gc")
        return 0

    monkeypatch.setattr(gc, "collect", _fake_collect)

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
        )

    assert pool is None


def test_seq_pipeline_adaptive_selects_process_executor_class() -> None:
    class _ProcessPolicy(AdaptivePolicy):
        def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
            _ = plan
            _ = runtime
            _ = tuning
            return ADAPTIVE_BACKEND_PROCESS

    calls = []

    class _DummyExecutor:
        def __init__(self, *, max_workers):  # type: ignore[no-untyped-def]
            calls.append(int(max_workers))

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            _ = exc_type
            _ = exc
            _ = tb
            return False

    overrides = PipelineOverrides(
        adaptive_policy=_ProcessPolicy(),
        adaptive_tuning=AdaptiveTuning(max_workers=2),
        adaptive_process_executor_cls=_DummyExecutor,
    )
    pipeline = _make_pipeline(overrides=overrides)
    assert list(pipeline.run(main_rows=[])) == []
    assert calls == [2]


def test_seq_pipeline_adaptive_selects_async_executor_class() -> None:
    class _AsyncPolicy(AdaptivePolicy):
        def choose_backend(self, *, plan, runtime, tuning):  # type: ignore[override]
            _ = plan
            _ = runtime
            _ = tuning
            return ADAPTIVE_BACKEND_ASYNC

    calls = []

    class _DummyExecutor:
        def __init__(self, *, max_workers):  # type: ignore[no-untyped-def]
            calls.append(int(max_workers))

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            _ = exc_type
            _ = exc
            _ = tb
            return False

    overrides = PipelineOverrides(
        adaptive_policy=_AsyncPolicy(),
        adaptive_tuning=AdaptiveTuning(max_workers=2),
        adaptive_async_executor_cls=_DummyExecutor,
    )
    pipeline = _make_pipeline(overrides=overrides)
    assert list(pipeline.run(main_rows=[])) == []
    assert calls == [2]


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
def test_stage_spans_emitted(monkeypatch, sink_mode: str) -> None:
    import scalim.execution.executor.batch.executor as batch_mod

    tick = {"t": 0.0}

    def _fake_time() -> float:
        tick["t"] += 0.01
        return tick["t"]

    monkeypatch.setattr(batch_mod.time, "time", _fake_time)

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
