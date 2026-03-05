import concurrent.futures as concurrent_futures
from typing import List, Optional

import pytest

from scalim.execution.context import BatchContext
from scalim.execution import ScalimEngine
from scalim.execution.executor.batch.executor import BatchExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.base._row_emission import RowEmissionCoordinator
from scalim.execution.pipeline.base.pipeline import SeqPipeline
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning import PlanBuilder
from scalim.planning.operators import LoadOperatorIr, LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, OrderByKeyIr, SourceIr
from tests.testing_utils import RecordingLoadRefExecutor


def _make_main_source() -> MainSourceIr:
    return MainSourceIr(source_id="main", loader=lambda: [])


def _make_source(source_id: str = "customers") -> SourceIr:
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable=lambda: {}),
    )


def _make_plan(
    field_specs: dict,
    target_fields: list,
    operators=(),
) -> ExecutionPlan:
    return ExecutionPlan(
        operators=operators,
        field_specs=field_specs,
        target_fields=target_fields,
    )


def _make_pipeline(
    plan: ExecutionPlan,
    demand: DemandIr,
    runtime_main_source: Optional[MainSourceIr],
    overrides: Optional[PipelineOverrides] = None,
) -> SeqPipeline:
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, runtime_main_source)
    executor = BatchExecutor(plan, runtime)
    return SeqPipeline(plan, executor, runtime, hook_manager, observer_manager, demand, batch_size=2, overrides=overrides)


class _CaptureHook(BaseHook):
    def __init__(self) -> None:
        self.row_writes = []
        self.row_releases = []
        self.column_writes = []
        self.field_slims = []

    def on_row_write(self, event) -> None:  # type: ignore[override]
        self.row_writes.append(event)

    def on_row_release(self, event) -> None:  # type: ignore[override]
        self.row_releases.append(event)

    def on_column_write(self, event) -> None:  # type: ignore[override]
        self.column_writes.append(event)

    def on_field_slim(self, event) -> None:  # type: ignore[override]
        self.field_slims.append(event)


@pytest.mark.parametrize(
    "has_other_field,main_rows,required_fields",
    [
        (False, None, None),
        (True, {0: {"id": 1}}, {"other"}),
    ],
    ids=["no-main-rows", "no-main-fields"],
)
def test_batch_executor_prefill_noop(has_other_field: bool, main_rows, required_fields) -> None:
    main_source = _make_main_source()
    field_specs = {}
    target_fields = []
    if has_other_field:
        other_source = _make_source("other")
        other_field = FieldIr(field_id="other", name="Other", source=other_source)
        field_specs = {"other": other_field}
        target_fields = ["other"]

    plan = _make_plan(field_specs, target_fields)
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source)
    executor = BatchExecutor(plan, runtime)
    context = BatchContext()

    executor.prefill_main_source_fields(context, main_rows=main_rows, required_fields=required_fields)

    assert context.get_field_count() == 0


def _make_loadref_op(*, field_key: str, source: SourceIr, step: LookupStepIr) -> LoadRefOperatorIr:
    field_spec = FieldIr(field_id=field_key, name=field_key, source=source)
    return LoadRefOperatorIr(
        operator_id="load_ref_{}".format(field_key),
        operator_type=OperatorType.LOAD_REF.value,
        source=source,
        field_key=field_key,
        field_spec=field_spec,
        lookup_steps=(step,),
    )


def test_batch_executor_seq_loadref_segment_returns_when_executor_missing() -> None:
    binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="keys")
    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    op = _make_loadref_op(field_key="x", source=source, step=LookupStepIr(from_field="id", to_source=source, bind=binding))

    plan = ExecutionPlan(operators=(op,))
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))
    executor = BatchExecutor(plan, runtime)
    executor._executors.pop(OperatorType.LOAD_REF.value, None)

    executor._execute_loadref_segment(  # noqa: SLF001
        [op],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
        adaptive_pool=None,
        max_workers=1,
        after_operator=None,
    )


def test_batch_executor_adaptive_loadref_segment_falls_back_to_serial_when_no_pool() -> None:
    binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="keys")
    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    step = LookupStepIr(from_field="id", to_source=source, bind=binding)
    op1 = _make_loadref_op(field_key="a", source=source, step=step)
    op2 = _make_loadref_op(field_key="b", source=source, step=step)

    plan = ExecutionPlan(operators=(op1, op2))
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader=lambda: []),
        parallel_mode="adaptive",
        max_workers=1,
    )
    executor = BatchExecutor(plan, runtime)

    seen: List[str] = []
    executor._executors[OperatorType.LOAD_REF.value] = RecordingLoadRefExecutor(seen)  # type: ignore[attr-defined]

    after: List[str] = []

    def _after(op: LoadRefOperatorIr) -> None:
        after.append(op.field_key)

    executor._execute_loadref_segment(  # noqa: SLF001
        [op1, op2],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
        adaptive_pool=None,
        max_workers=1,
        after_operator=_after,
    )

    assert seen == ["a", "b"]
    assert after == ["a", "b"]


def test_batch_executor_adaptive_loadref_segment_returns_when_executor_missing() -> None:
    binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="keys")
    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    op = _make_loadref_op(field_key="x", source=source, step=LookupStepIr(from_field="id", to_source=source, bind=binding))

    plan = ExecutionPlan(operators=(op,))
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=MainSourceIr(source_id="main", loader=lambda: []),
        parallel_mode="adaptive",
        max_workers=1,
    )
    executor = BatchExecutor(plan, runtime)
    executor._executors.pop(OperatorType.LOAD_REF.value, None)

    executor._execute_loadref_segment(  # noqa: SLF001
        [op],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        required_fields=None,
        adaptive_pool=None,
        max_workers=1,
        after_operator=None,
    )


def test_pipeline_iter_row_batches_empty() -> None:
    def _fake_chunk_iterable(_iterable, _chunk_size):  # type: ignore[no-untyped-def]
        return iter([[]])

    overrides = PipelineOverrides(chunk_iterable=_fake_chunk_iterable)
    main_source = _make_main_source()
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)
    plan = _make_plan({}, [])
    pipeline = _make_pipeline(plan, demand, main_source, overrides=overrides)

    assert list(pipeline._iter_row_batches([{"id": 1}])) == []


def test_adaptive_pipeline_uses_overridden_adaptive_executor_cls() -> None:
    class _TrackingThreadPoolExecutor(concurrent_futures.ThreadPoolExecutor):
        created: int = 0

        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            type(self).created += 1
            super().__init__(*args, **kwargs)

    overrides = PipelineOverrides(adaptive_executor_cls=_TrackingThreadPoolExecutor)

    main_source = _make_main_source()
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)
    plan = _make_plan({}, [])

    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        parallel_mode="adaptive",
        batch_size=1,
        max_workers=2,
        pipeline_overrides=overrides,
    )

    _ = engine.run(main_rows=[])

    assert _TrackingThreadPoolExecutor.created == 1


@pytest.mark.parametrize(
    "use_runtime_main_source,expect_missing_field",
    [
        (False, False),
        (True, True),
    ],
    ids=["no-runtime-source", "missing-field-spec"],
)
def test_pipeline_write_main_source_columns_variants(
    use_runtime_main_source: bool,
    expect_missing_field: bool,
) -> None:
    main_source = _make_main_source()
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)
    plan = _make_plan({}, ["missing_field"])
    runtime_main_source = main_source if use_runtime_main_source else None
    pipeline = _make_pipeline(plan, demand, runtime_main_source=runtime_main_source)

    context = BatchContext()
    sink = InMemoryColumnSink()

    pipeline._write_main_source_columns([0], context, sink, batch_num=1)

    if expect_missing_field:
        assert "missing_field" in sink.get_columns()
    else:
        assert sink.get_columns() == {}


def test_pipeline_write_column_if_target_skips_non_target() -> None:
    main_source = _make_main_source()
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)
    plan = _make_plan({}, ["target"])
    pipeline = _make_pipeline(plan, demand, main_source)

    context = BatchContext()
    sink = InMemoryColumnSink()

    pipeline._write_column_if_target("not_target", [0], context, sink, batch_num=1)

    assert sink.get_columns() == {}


def test_pipeline_execute_batch_column_mode_handles_load_operator() -> None:
    main_source = _make_main_source()
    customers_source = _make_source("customers")
    customer_field = FieldIr(field_id="customer_name", name="Customer", source=customers_source)
    demand = DemandIr.from_irs(sources=[customers_source], fields=[customer_field], main_source=main_source)

    load_op = LoadOperatorIr(
        operator_id="load_0",
        operator_type=OperatorType.LOAD.value,
        source=customers_source,
        field_keys=("customer_name",),
        is_primary=False,
    )
    plan = _make_plan({"customer_name": customer_field}, ["customer_name"], operators=(load_op,))
    pipeline = _make_pipeline(plan, demand, main_source)

    row_ids = [0, 1]
    batch_rows = {0: {"id": 1}, 1: {"id": 2}}
    sink = InMemoryColumnSink()

    pipeline._execute_batch_column_mode(row_ids, batch_rows, sink, batch_num=1)

    assert "customer_name" in sink.get_columns()


def test_pipeline_execute_batch_streaming_mode_writes_load_operator_fields() -> None:
    main_source = _make_main_source()
    customers_source = _make_source("customers")
    customer_field = FieldIr(field_id="customer_name", name="Customer", source=customers_source)
    demand = DemandIr.from_irs(sources=[customers_source], fields=[customer_field], main_source=main_source)

    load_op = LoadOperatorIr(
        operator_id="load_0",
        operator_type=OperatorType.LOAD.value,
        source=customers_source,
        field_keys=("customer_name",),
        is_primary=False,
    )
    plan = _make_plan({"customer_name": customer_field}, ["customer_name"], operators=(load_op,))
    pipeline = _make_pipeline(plan, demand, main_source)

    row_ids = [0]
    batch_rows = {0: {"id": 1}}
    sink = InMemoryRowSink()

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)

    assert sink.get_data()


def test_pipeline_true_row_streaming_writes_null_fk_row_before_ref_loader_call() -> None:
    sink = InMemoryRowSink()

    def _build_keys_params(field_name: str, param_name: str):  # type: ignore[no-untyped-def]
        def _builder(ctx):  # type: ignore[no-untyped-def]
            return (), {param_name: set(ctx.lookup_keys or set())}

        return BindingIr(key_field=field_name, params_builder=_builder, mode="keys")

    def _load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        written = sink.get_data()
        assert len(written) == 1
        assert written[0]["order_id"] == 0
        _ = customer_id_set
        return {100: {"customer_id": 100, "customer_name": "Alice"}}

    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable=_load_customers, bindings={"customer_id": _build_keys_params("customer_id", "customer_id_set")}),
    )

    fields = [
        FieldIr(field_id="order_id", name="Order", source=main_source, is_primary=True),
        FieldIr(
            field_id="customer_name",
            name="Customer",
            source=customers,
            data_key="customer_name",
            relation=main_source["customer_id"].join(customers["customer_id"]),
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers], fields=fields, main_source=main_source)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])
    pipeline = _make_pipeline(plan, demand, main_source)

    row_ids = [0, 1]
    batch_rows = {0: {"order_id": 0, "customer_id": None}, 1: {"order_id": 1, "customer_id": 100}}

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)

    assert [row["customer_name"] for row in sink.get_data()] == [None, "Alice"]


def test_pipeline_true_row_streaming_releases_written_rows_before_next_compute_row() -> None:
    sink = InMemoryRowSink()
    capture = _CaptureHook()

    calls = []

    def _compute_b(a):  # type: ignore[no-untyped-def]
        calls.append("b")
        if len(calls) == 2:
            assert len(sink.get_data()) == 1
            assert len(capture.row_releases) == 1
        return a * 10

    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    id_field = FieldIr(field_id="id", name="ID", source=main_source, is_primary=True)
    a_field = DerivedFieldIr(field_id="a", name="A", dependencies=("id",), calculator=lambda id: id)
    b_field = DerivedFieldIr(field_id="b", name="B", dependencies=("a",), calculator=_compute_b)

    demand = DemandIr.from_irs(sources=[], fields=[id_field, a_field, b_field], main_source=main_source)
    plan = PlanBuilder(demand).build(targets=["a", "b"])
    pipeline = _make_pipeline(plan, demand, main_source)
    pipeline.hook_manager.register(capture)

    row_ids = [0, 1]
    batch_rows = {0: {"id": 1}, 1: {"id": 2}}

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)

    assert len(sink.get_data()) == 2
    assert len(calls) == 2
    assert len(capture.row_writes) == 2
    assert len(capture.row_releases) == 2


def test_batch_context_disable_row_skips_set_field_value() -> None:
    ctx = BatchContext()
    ctx.set_field_value("a", 0, 1)
    ctx.disable_row(0)
    ctx.set_field_value("a", 0, 2)
    assert ctx.get_field_value("a", 0) == 1


def test_pipeline_resolve_streaming_global_ready_target_fields_includes_passthrough_target() -> None:
    main_source = _make_main_source()
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)
    plan = _make_plan({}, ["passthrough"])
    pipeline = _make_pipeline(plan, demand, main_source)

    assert pipeline._resolve_streaming_global_ready_target_fields() == {"passthrough"}


def test_pipeline_collect_streaming_rows_binding_barriers_skips_steps_without_binding() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(callable=lambda: {}),
    )

    fields = [
        FieldIr(
            field_id="customer_name",
            name="Customer",
            source=customers,
            data_key="customer_name",
            relation=main_source["customer_id"].join(customers["customer_id"]),
        )
    ]

    demand = DemandIr.from_irs(sources=[customers], fields=fields, main_source=main_source)
    plan = PlanBuilder(demand).build(targets=["customer_name"])
    pipeline = _make_pipeline(plan, demand, main_source)

    rows_binding_relations, rows_binding_ops = pipeline._collect_streaming_rows_binding_barriers()

    assert rows_binding_relations == set()
    assert rows_binding_ops == set()


def test_row_emission_coordinator_flush_noops_when_write_order_missing() -> None:
    plan = _make_plan({}, ["a"])
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), _make_main_source())
    sink = InMemoryRowSink()
    coordinator = RowEmissionCoordinator(
        runtime=runtime,
        sink=sink,
        target_fields=["a"],
        retained_fields=set(),
        global_ready_fields=set(),
        allow_release=True,
    )
    coordinator.attach_context(BatchContext())

    coordinator.on_field_set("a", 0)

    assert sink.get_data() == []


def test_row_emission_coordinator_defers_release_when_disabled() -> None:
    plan = _make_plan({}, ["a"])
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), _make_main_source())
    sink = InMemoryRowSink()
    coordinator = RowEmissionCoordinator(
        runtime=runtime,
        sink=sink,
        target_fields=["a"],
        retained_fields=set(),
        global_ready_fields=set(),
        allow_release=False,
    )
    ctx = BatchContext()
    ctx.set_field_value("a", 0, 1)
    coordinator.attach_context(ctx)
    coordinator.set_write_order([0])

    coordinator.on_field_set("a", 0)

    assert sink.get_data()
    assert coordinator.drain_rows_to_remove() == set()


def test_row_emission_coordinator_finalize_writes_rows_even_when_not_ready() -> None:
    plan = _make_plan({}, ["a"])
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), _make_main_source())
    sink = InMemoryRowSink()
    coordinator = RowEmissionCoordinator(
        runtime=runtime,
        sink=sink,
        target_fields=["a"],
        retained_fields=set(),
        global_ready_fields=set(),
        allow_release=False,
    )
    ctx = BatchContext()
    ctx.set_field_value("a", 0, 1)
    coordinator.attach_context(ctx)
    coordinator.set_write_order([0])

    coordinator.finalize()

    assert sink.get_data() == [{"a": 1}]


def test_pipeline_streaming_order_by_sorts_rows_and_stable() -> None:
    main_source = MainSourceIr(
        source_id="main",
        loader=lambda: [],
        order_by=(OrderByKeyIr(field_key="order_id", direction="asc"),),
    )
    field_spec = FieldIr(field_id="order_id", name="Order", source=main_source, is_primary=True)
    demand = DemandIr.from_irs(sources=[], fields=[field_spec], main_source=main_source)
    plan = _make_plan({"order_id": field_spec}, ["order_id"])
    pipeline = _make_pipeline(plan, demand, main_source)

    capture = _CaptureHook()
    pipeline.hook_manager.register(capture)

    row_ids = [0, 1, 2]
    batch_rows = {0: {"order_id": 2}, 1: {"order_id": 1}, 2: {"order_id": 2}}
    sink = InMemoryRowSink()

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)

    assert [row["order_id"] for row in sink.get_data()] == [1, 2, 2]
    assert [event.row_id for event in capture.row_writes] == [1, 0, 2]


def test_pipeline_streaming_order_by_desc_nulls_last() -> None:
    main_source = MainSourceIr(
        source_id="main",
        loader=lambda: [],
        order_by=(OrderByKeyIr(field_key="score", direction="desc"),),
    )
    field_spec = FieldIr(field_id="score", name="Score", source=main_source, is_primary=True)
    demand = DemandIr.from_irs(sources=[], fields=[field_spec], main_source=main_source)
    plan = _make_plan({"score": field_spec}, ["score"])
    pipeline = _make_pipeline(plan, demand, main_source)

    row_ids = [0, 1, 2, 3]
    batch_rows = {0: {"score": None}, 1: {"score": 3}, 2: {"score": 5}, 3: {"score": 5}}
    sink = InMemoryRowSink()

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)

    assert [row["score"] for row in sink.get_data()] == [5, 5, 3, None]


def test_pipeline_column_order_by_sets_row_ids() -> None:
    main_source = MainSourceIr(
        source_id="main",
        loader=lambda: [],
        order_by=(OrderByKeyIr(field_key="order_id", direction="asc"),),
    )
    field_spec = FieldIr(field_id="order_id", name="Order", source=main_source, is_primary=True)
    demand = DemandIr.from_irs(sources=[], fields=[field_spec], main_source=main_source)
    plan = _make_plan({"order_id": field_spec}, ["order_id"])
    pipeline = _make_pipeline(plan, demand, main_source)

    row_ids = [0, 1, 2]
    batch_rows = {0: {"order_id": 3}, 1: {"order_id": 1}, 2: {"order_id": 2}}
    sink = InMemoryColumnSink()

    pipeline._execute_batch_column_mode(row_ids, batch_rows, sink, batch_num=1)

    assert sink.get_row_ids() == [1, 2, 0]


def test_pipeline_streaming_mode_emits_row_events() -> None:
    main_source = _make_main_source()
    field_spec = FieldIr(field_id="id", name="ID", source=main_source)
    demand = DemandIr.from_irs(sources=[], fields=[field_spec], main_source=main_source)
    plan = _make_plan({"id": field_spec}, ["id"])

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, main_source)
    executor = BatchExecutor(plan, runtime)
    pipeline = SeqPipeline(plan, executor, runtime, hook_manager, observer_manager, demand, batch_size=2)

    row_ids = [0, 1]
    batch_rows = {0: {"id": 1}, 1: {"id": 2}}

    pipeline._execute_batch_streaming_mode(row_ids, batch_rows, InMemoryRowSink(), batch_num=1)

    assert len(hook.row_writes) == 2
    assert len(hook.row_releases) == 2


def test_pipeline_column_mode_emits_column_events() -> None:
    main_source = _make_main_source()
    field_spec = FieldIr(field_id="id", name="ID", source=main_source)
    demand = DemandIr.from_irs(sources=[], fields=[field_spec], main_source=main_source)
    plan = _make_plan({"id": field_spec}, ["id"])

    hook = _CaptureHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, main_source)
    executor = BatchExecutor(plan, runtime)
    pipeline = SeqPipeline(plan, executor, runtime, hook_manager, observer_manager, demand, batch_size=2)

    row_ids = [0]
    batch_rows = {0: {"id": 1}}

    pipeline._execute_batch_column_mode(row_ids, batch_rows, InMemoryColumnSink(), batch_num=1)

    assert len(hook.column_writes) == 1
    assert len(hook.field_slims) == 1
