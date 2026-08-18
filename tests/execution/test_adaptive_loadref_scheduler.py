from concurrent.futures import Future
import warnings
from typing import Dict, List, Tuple, cast

import pytest

from scalim.execution.adaptive import loadref_scheduler
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.adaptive.strategy_unit import collect_layer_executable_ops
from scalim.execution.context import BatchContext
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.utils.relation_signature import build_relation_signature, has_rows_binding
from tests.support.testing_utils import InlineExecutor, NoOpLoadRefExecutor, RecordingLoadRefExecutor


def test_resolve_adaptive_max_workers_auto_uses_cpu_count() -> None:
    assert loadref_scheduler.resolve_adaptive_max_workers(0, cpu_count_fn=lambda: None) == 5
    assert loadref_scheduler.resolve_adaptive_max_workers(3) == 3


def test_resolve_adaptive_max_workers_explicit_cap_emits_warning() -> None:
    with pytest.warns(
        UserWarning,
        match=r"`adaptive` 模式 `max_workers` 被护栏裁剪: 请求=1000 解析=32 上限=32 `cpu_count`=4",
    ):
        assert loadref_scheduler.resolve_adaptive_max_workers(1000, cpu_count_fn=lambda: 4) == 32


def test_resolve_adaptive_max_workers_explicit_below_cap_no_warning() -> None:
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        assert loadref_scheduler.resolve_adaptive_max_workers(10, cpu_count_fn=lambda: 4) == 10
    assert recorded == []


def test_build_layers_splits_layers_and_falls_back_on_cycle() -> None:
    layers = loadref_scheduler._build_layers(  # noqa: SLF001
        ["a", "b", "c"],
        deps={"b": ("a",), "c": ("b",)},
    )
    assert layers == [["a"], ["b"], ["c"]]

    layers = loadref_scheduler._build_layers(  # noqa: SLF001
        ["a", "b"],
        deps={"a": ("b",), "b": ("a",)},
    )
    assert layers == [["a", "b"]]


_SOURCE_REGISTRY: Dict[str, SourceIr] = {}


def _make_loadref_op(
    *,
    field_key: str,
    to_source: SourceIr,
    lookup_steps: Tuple[LookupStepIr, ...],
) -> LoadRefOperatorIr:
    _SOURCE_REGISTRY[str(to_source.source_id)] = to_source
    return LoadRefOperatorIr(
        operator_id="load_ref_{}".format(field_key),
        operator_type=OperatorType.LOAD_REF.value,
        source_id=to_source.source_id,
        field_key=field_key,
        lookup_steps=lookup_steps,
    )


def _make_runtime(plan: ExecutionPlan, *, main_source=None, sources=None, runtime_bindings: RuntimeBindings = None) -> ExecutionRuntime:  # type: ignore[assignment]
    if sources is None:
        collected = {}
        for op in plan.operators:
            if not isinstance(op, LoadRefOperatorIr):
                continue
            for step in op.lookup_steps:
                live = _SOURCE_REGISTRY.get(str(step.to_source_id))
                if live is not None:
                    collected[str(step.to_source_id)] = live
        sources = collected
    return ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main_source=main_source,
        sources=sources or {},
        runtime_bindings=runtime_bindings or RuntimeBindings(),
    )


def test_has_rows_binding_handles_missing_and_rows() -> None:
    no_binding_source = SourceIr(
        source_id="s0",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s0.loader")),
    )

    rows_binding = BindingIr(
        key_field="id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="s1.id.rows_binding"),
        mode="rows",
    )
    rows_binding_source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )

    op = _make_loadref_op(
        field_key="x",
        to_source=rows_binding_source,
        lookup_steps=(
            LookupStepIr(from_field="id", to_source_id=no_binding_source.source_id),
            LookupStepIr(from_field="id", to_source_id=rows_binding_source.source_id, bind=rows_binding),
        ),
    )

    assert (
        has_rows_binding(
            op.lookup_steps,
            {"s0": no_binding_source, "s1": rows_binding_source},
        )
        is True
    )


def test_collect_layer_executable_ops_skips_executed_group_and_calls_after_operator() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    op = _make_loadref_op(field_key="a", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source_id=source.source_id),))
    plan = ExecutionPlan()
    runtime = _make_runtime(plan, main_source=None, sources={source.source_id: source})
    runtime.load_ref_group_executed.add(build_relation_signature(op.lookup_steps, {source.source_id: source}))

    after_calls: List[str] = []

    def _after(operator: LoadRefOperatorIr) -> None:
        after_calls.append(operator.field_key)

    skipped_field_keys, executable_ops = collect_layer_executable_ops((op,), runtime=runtime, after_operator=_after)
    assert skipped_field_keys == {"a"}
    assert executable_ops == []
    assert after_calls == ["a"]

    skipped_field_keys, executable_ops = collect_layer_executable_ops((op,), runtime=runtime, after_operator=None)
    assert skipped_field_keys == {"a"}
    assert executable_ops == []


def test_adaptive_scheduler_repr_and_empty_ops_returns() -> None:
    plan = ExecutionPlan()
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    assert "AdaptiveLoadRefScheduler" in repr(scheduler)

    runtime = _make_runtime(plan, main_source=None)
    scheduler.execute_segment(
        [],
        context=BatchContext(),
        batch_row_nth=[],
        runtime=runtime,
        pool=None,
        max_workers=1,
        required_fields=None,
        after_operator=None,
    )


def test_adaptive_scheduler_rows_barrier_serializes_and_calls_after_operator() -> None:
    rows_binding = BindingIr(
        key_field="id",
        params_builder_ref=RuntimeHandleIdIr(handle_id="s1.id.rows_binding"),
        mode="rows",
    )
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )

    op_rows = _make_loadref_op(
        field_key="rows",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source.source_id, bind=rows_binding),),
    )
    op_keys = _make_loadref_op(
        field_key="keys",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source.source_id),),
    )

    plan = ExecutionPlan(
        operators=(op_rows, op_keys),
        ref_loader_sequence=[(source, [("rows", ()), ("keys", ())])],
    )
    runtime = _make_runtime(plan, main_source=None)

    calls: List[str] = []

    after_calls: List[str] = []

    def _after(op: LoadRefOperatorIr) -> None:
        after_calls.append(op.field_key)

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_loadref_executor_factory=lambda: RecordingLoadRefExecutor(calls)),
    )
    scheduler.execute_segment(
        [op_rows, op_keys],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=object(),
        max_workers=4,
        required_fields=None,
        after_operator=_after,
    )

    assert calls == ["rows", "keys"]
    assert after_calls == ["rows", "keys"]


def test_adaptive_scheduler_serial_fallback_executes_and_calls_after_operator() -> None:
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    op1 = _make_loadref_op(
        field_key="a",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source.source_id),),
    )
    op2 = _make_loadref_op(
        field_key="b",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source.source_id),),
    )

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = _make_runtime(plan, main_source=None)

    calls: List[str] = []

    after_calls: List[str] = []

    def _after(op: LoadRefOperatorIr) -> None:
        after_calls.append(op.field_key)

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_loadref_executor_factory=lambda: RecordingLoadRefExecutor(calls)),
    )
    scheduler.execute_segment(
        [op1, op2],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=None,
        max_workers=4,
        required_fields=None,
        after_operator=_after,
    )

    assert calls == ["a", "b"]
    assert after_calls == ["a", "b"]


def test_adaptive_scheduler_exception_propagates_and_cancels_futures_best_effort() -> None:
    class _TrackingFuture(Future):
        cancelled_calls: int = 0

        def cancel(self) -> bool:  # type: ignore[override]
            type(self).cancelled_calls += 1
            return super().cancel()

    class _InlineExecutor:
        def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
            fut = _TrackingFuture()
            try:
                fut.set_result(fn(*args, **kwargs))
            except Exception as e:  # noqa: BLE001
                fut.set_exception(e)
            return fut

    source_ok = SourceIr(
        source_id="s_ok",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s_ok.loader")),
    )
    source_boom = SourceIr(
        source_id="s_boom",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s_boom.loader")),
    )
    op1 = _make_loadref_op(
        field_key="ok",
        to_source=source_ok,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source_ok.source_id),),
    )
    op2 = _make_loadref_op(
        field_key="boom",
        to_source=source_boom,
        lookup_steps=(LookupStepIr(from_field="id", to_source_id=source_boom.source_id),),
    )

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source_ok, [("ok", ())]), (source_boom, [("boom", ())])],
    )
    runtime = _make_runtime(plan, main_source=None)

    class _BoomExecutor:
        def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
            op = cast("LoadRefOperatorIr", operator)  # pragma: allow-cast test executor typed narrowing
            if op.field_key == "boom":
                raise RuntimeError("boom")
            context.set_field_value(op.field_key, batch_row_nth[0], 1)
            _ = runtime

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_min_parallel_tasks=1, adaptive_loadref_executor_factory=_BoomExecutor),
    )
    with pytest.raises(RuntimeError, match="boom"):
        scheduler.execute_segment(
            [op1, op2],
            context=BatchContext(),
            batch_row_nth=[0],
            runtime=runtime,
            pool=_InlineExecutor(),
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )

    assert _TrackingFuture.cancelled_calls == 2


def test_adaptive_scheduler_skips_relation_already_executed_but_calls_after_operator() -> None:
    class _SubmitTrackingExecutor:
        called: int = 0

        def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
            type(self).called += 1
            fut: "Future[object]" = Future()
            fut.set_result(fn(*args, **kwargs))
            return fut

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    steps = (LookupStepIr(from_field="id", to_source_id=source.source_id),)
    op1 = _make_loadref_op(field_key="a", to_source=source, lookup_steps=steps)
    op2 = _make_loadref_op(field_key="b", to_source=source, lookup_steps=steps)

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = _make_runtime(plan, main_source=None)
    runtime.load_ref_group_executed.add(loadref_scheduler.build_relation_signature(steps, {source.source_id: source}))

    after_calls: List[str] = []

    def _after(op: LoadRefOperatorIr) -> None:
        after_calls.append(op.field_key)

    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    scheduler.execute_segment(
        [op1, op2],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=_SubmitTrackingExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=_after,
    )

    assert after_calls == ["a", "b"]
    assert _SubmitTrackingExecutor.called == 0


def test_adaptive_scheduler_skips_some_ops_in_layer_commit_loop() -> None:
    source_skipped = SourceIr(
        source_id="skipped",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="skipped.loader")),
    )
    source_exec = SourceIr(
        source_id="exec",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="exec.loader")),
    )

    steps_skipped = (LookupStepIr(from_field="id", to_source_id=source_skipped.source_id),)
    steps_exec = (LookupStepIr(from_field="id", to_source_id=source_exec.source_id),)

    op_skipped = _make_loadref_op(field_key="skip", to_source=source_skipped, lookup_steps=steps_skipped)
    op1 = _make_loadref_op(field_key="a", to_source=source_exec, lookup_steps=steps_exec)
    op2 = _make_loadref_op(field_key="b", to_source=source_exec, lookup_steps=steps_exec)

    plan = ExecutionPlan(
        operators=(op_skipped, op1, op2),
        ref_loader_sequence=[
            (source_skipped, [("skip", ())]),
            (source_exec, [("a", ()), ("b", ())]),
        ],
    )
    runtime = _make_runtime(plan, main_source=None)
    runtime.load_ref_group_executed.add(
        loadref_scheduler.build_relation_signature(steps_skipped, {source_skipped.source_id: source_skipped})
    )

    after_calls: List[str] = []

    def _after(op: LoadRefOperatorIr) -> None:
        after_calls.append(op.field_key)

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_min_parallel_tasks=1, adaptive_loadref_executor_factory=NoOpLoadRefExecutor),
    )
    scheduler.execute_segment(
        [op_skipped, op1, op2],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=_after,
    )

    assert after_calls == ["skip", "a", "b"]


def test_adaptive_scheduler_relation_tasks_write_all_group_fields() -> None:
    loader_calls: List[bool] = []

    def _loader() -> dict:
        loader_calls.append(True)
        return {1: {"a": "A", "b": "B"}}

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
    )
    steps = (LookupStepIr(from_field="id", to_source_id=source.source_id),)
    op1 = _make_loadref_op(field_key="a", to_source=source, lookup_steps=steps)
    op2 = _make_loadref_op(field_key="b", to_source=source, lookup_steps=steps)

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = _make_runtime(
        plan,
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources={"s1": source},
        runtime_bindings=RuntimeBindings(
            main_source_loaders={"main": lambda: []},
            source_loaders={"s1": _loader},
        ),
    )

    context = BatchContext()
    context.set_field_value("id", 0, 1)

    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides(adaptive_min_parallel_tasks=1))
    scheduler.execute_segment(
        [op1, op2],
        context=context,
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )
    assert context.get_field_value("a", 0) == "A"
    assert context.get_field_value("b", 0) == "B"
    assert len(loader_calls) == 1
