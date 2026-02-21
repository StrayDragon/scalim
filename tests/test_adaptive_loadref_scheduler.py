from concurrent.futures import Future
from typing import List, Tuple, cast

import pytest

from scalim.execution.adaptive import loadref_scheduler
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.context import BatchContext
from scalim.execution.executor.helpers.relation_signature import has_rows_binding
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from tests.testing_utils import InlineExecutor, NoOpLoadRefExecutor, RecordingLoadRefExecutor


def test_resolve_adaptive_max_workers_auto_uses_cpu_count(monkeypatch) -> None:
    monkeypatch.setattr(loadref_scheduler.os, "cpu_count", lambda: None)
    assert loadref_scheduler.resolve_adaptive_max_workers(0) == 5
    assert loadref_scheduler.resolve_adaptive_max_workers(3) == 3


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


def _make_loadref_op(
    *,
    field_key: str,
    to_source: SourceIr,
    lookup_steps: Tuple[LookupStepIr, ...],
) -> LoadRefOperatorIr:
    field_spec = FieldIr(field_id=field_key, name=field_key, source=to_source)
    return LoadRefOperatorIr(
        operator_id="load_ref_{}".format(field_key),
        operator_type=OperatorType.LOAD_REF.value,
        source=to_source,
        field_key=field_key,
        field_spec=field_spec,
        lookup_steps=lookup_steps,
    )


def test_has_rows_binding_handles_missing_and_rows() -> None:
    no_binding_source = SourceIr(source_id="s0", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))

    rows_binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="rows")
    rows_binding_source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))

    op = _make_loadref_op(
        field_key="x",
        to_source=rows_binding_source,
        lookup_steps=(
            LookupStepIr(from_field="id", to_source=no_binding_source),
            LookupStepIr(from_field="id", to_source=rows_binding_source, bind=rows_binding),
        ),
    )

    assert has_rows_binding(op.lookup_steps) is True


def test_adaptive_scheduler_repr_and_empty_ops_returns() -> None:
    plan = ExecutionPlan()
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    assert "AdaptiveLoadRefScheduler" in repr(scheduler)

    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)
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
    rows_binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="rows")
    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))

    op_rows = _make_loadref_op(
        field_key="rows",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source, bind=rows_binding),),
    )
    op_keys = _make_loadref_op(
        field_key="keys",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source),),
    )

    plan = ExecutionPlan(
        operators=(op_rows, op_keys),
        ref_loader_sequence=[(source, [("rows", ()), ("keys", ())])],
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))

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
    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    op1 = _make_loadref_op(
        field_key="a",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source),),
    )
    op2 = _make_loadref_op(
        field_key="b",
        to_source=source,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source),),
    )

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))

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

    source_ok = SourceIr(source_id="s_ok", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    source_boom = SourceIr(source_id="s_boom", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    op1 = _make_loadref_op(
        field_key="ok",
        to_source=source_ok,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source_ok),),
    )
    op2 = _make_loadref_op(
        field_key="boom",
        to_source=source_boom,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source_boom),),
    )

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source_ok, [("ok", ())]), (source_boom, [("boom", ())])],
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))

    class _BoomExecutor:
        def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
            op = cast("LoadRefOperatorIr", operator)
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

    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    steps = (LookupStepIr(from_field="id", to_source=source),)
    op1 = _make_loadref_op(field_key="a", to_source=source, lookup_steps=steps)
    op2 = _make_loadref_op(field_key="b", to_source=source, lookup_steps=steps)

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))
    runtime.load_ref_group_executed.add(loadref_scheduler.build_relation_signature(steps))

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
    source_skipped = SourceIr(source_id="skipped", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))
    source_exec = SourceIr(source_id="exec", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))

    steps_skipped = (LookupStepIr(from_field="id", to_source=source_skipped),)
    steps_exec = (LookupStepIr(from_field="id", to_source=source_exec),)

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
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))
    runtime.load_ref_group_executed.add(loadref_scheduler.build_relation_signature(steps_skipped))

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

    source = SourceIr(source_id="s1", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_loader))
    steps = (LookupStepIr(from_field="id", to_source=source),)
    op1 = _make_loadref_op(field_key="a", to_source=source, lookup_steps=steps)
    op2 = _make_loadref_op(field_key="b", to_source=source, lookup_steps=steps)

    plan = ExecutionPlan(
        operators=(op1, op2),
        ref_loader_sequence=[(source, [("a", ()), ("b", ())])],
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=MainSourceIr(source_id="main", loader=lambda: []))

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
