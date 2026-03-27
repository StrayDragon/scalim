import threading
import time
from typing import Any, Hashable, List, Tuple, cast

import pytest

from scalim.events.catalog import EVENT_ADAPTIVE_SCHEDULER_DECISION
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.context import BatchContext
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, SourceIr

from scalim.execution.adaptive.policy import (
    PROCESS_FAILURE_FAIL_FAST,
    AdaptiveLayerDecision,
    AdaptivePolicy,
)
from scalim.execution.adaptive.tuning import AdaptiveTuning
from tests.testing_utils import InlineExecutor, NoOpLoadRefExecutor, RecordingLoadRefExecutor


def _noop_loader(*_args: Any, **_kwargs: Any) -> dict:
    return {}


def _main_loader() -> list:
    return []


def _loader_a() -> dict:
    return {1: {"a": "a"}}


def _loader_b() -> dict:
    return {1: {"b": "b"}}


def _make_source(source_id: str) -> SourceIr:
    return SourceIr(source_id=source_id, key=KeyIr(key="id"), loader_spec=LoaderIr(callable=_noop_loader))


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


def test_adaptive_tuning_validation_and_defaults() -> None:
    tuning = AdaptiveTuning()
    tuning.validate()
    assert tuning.pool_for_source("customers") == "default"
    assert tuning.resolve_pool_limit("default", resolved_max_workers=4) == 4
    assert tuning.effective_min_parallel_tasks_per_layer() == 2


def test_adaptive_tuning_validation_rejects_invalid_config() -> None:
    with pytest.raises(ValueError, match="must be >= 1"):
        AdaptiveTuning(pools={"db": 0}).validate()

    with pytest.raises(ValueError, match="unknown pool"):
        AdaptiveTuning(pools={"db": 1}, source_pools={"customers": "missing"}).validate()


def test_adaptive_tuning_validation_covers_additional_error_branches() -> None:
    with pytest.raises(ValueError, match="pools keys must be non-empty"):
        AdaptiveTuning(pools={"": 1}).validate()

    with pytest.raises(ValueError, match="source_pools keys must be non-empty"):
        AdaptiveTuning(source_pools={"": "default"}).validate()

    with pytest.raises(ValueError, match="must be non-empty"):
        AdaptiveTuning(source_pools={"s1": ""}).validate()

    with pytest.raises(ValueError, match="min_parallel_tasks_per_layer"):
        AdaptiveTuning(min_parallel_tasks_per_layer=0).validate()

    with pytest.raises(ValueError, match="min_total_lookup_keys_per_layer"):
        AdaptiveTuning(min_total_lookup_keys_per_layer=-1).validate()

    with pytest.raises(ValueError, match="min_lookup_keys_per_task"):
        AdaptiveTuning(min_lookup_keys_per_task=-1).validate()

    tuning = AdaptiveTuning()
    assert tuning.resolve_pool_limit("unknown", resolved_max_workers=3) == 3


def test_adaptive_policy_decisions_and_pool_selection() -> None:
    policy = AdaptivePolicy()
    plan = ExecutionPlan()
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    op = _make_loadref_op(
        field_key="a", to_source=_make_source("s1"), lookup_steps=(LookupStepIr(from_field="id", to_source=_make_source("s1")),)
    )

    tuning = AdaptiveTuning(min_parallel_tasks_per_layer=3)
    decision = policy.decide_layer_parallelism(
        [op, op], tuning=tuning, runtime=runtime, pool_is_available=True, resolved_max_workers=4, layer_lookup_keys=None
    )
    assert decision.should_parallelize is False
    assert decision.reason == "below_min_parallel_tasks"

    tuning = AdaptiveTuning(min_total_lookup_keys_per_layer=10, min_parallel_tasks_per_layer=2)
    decision = policy.decide_layer_parallelism(
        [op, op],
        tuning=tuning,
        runtime=runtime,
        pool_is_available=True,
        resolved_max_workers=4,
        layer_lookup_keys={"a": 4, "b": 5},
    )
    assert decision.should_parallelize is False
    assert decision.reason == "below_min_total_lookup_keys"

    tuning = AdaptiveTuning(min_lookup_keys_per_task=3, min_parallel_tasks_per_layer=2)
    decision = policy.decide_layer_parallelism(
        [op, op],
        tuning=tuning,
        runtime=runtime,
        pool_is_available=True,
        resolved_max_workers=4,
        layer_lookup_keys={"a": 2, "b": 3},
    )
    assert decision.should_parallelize is False
    assert decision.reason == "below_min_lookup_keys_per_task"

    tuning = AdaptiveTuning(min_parallel_tasks_per_layer=2)
    decision = policy.decide_layer_parallelism(
        [op, op], tuning=tuning, runtime=runtime, pool_is_available=True, resolved_max_workers=4, layer_lookup_keys=None
    )
    assert decision.should_parallelize is True
    assert decision.reason is None

    tuning = AdaptiveTuning()
    assert policy.choose_process_failure_mode(plan=plan, runtime=runtime, tuning=tuning) == PROCESS_FAILURE_FAIL_FAST

    decision = policy.decide_layer_parallelism(
        [op],
        tuning=tuning,
        runtime=runtime,
        pool_is_available=False,
        resolved_max_workers=4,
        layer_lookup_keys=None,
    )
    assert decision.should_parallelize is False
    assert decision.reason == "no_pool"

    decision = policy.decide_layer_parallelism(
        [op],
        tuning=tuning,
        runtime=runtime,
        pool_is_available=True,
        resolved_max_workers=1,
        layer_lookup_keys=None,
    )
    assert decision.should_parallelize is False
    assert decision.reason == "single_worker"

    source_a = _make_source("a")
    source_b = _make_source("b")
    op_single = _make_loadref_op(field_key="single", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_multi = _make_loadref_op(
        field_key="multi",
        to_source=source_a,
        lookup_steps=(LookupStepIr(from_field="id", to_source=source_a), LookupStepIr(from_field="id", to_source=source_b)),
    )
    tuning = AdaptiveTuning(pools={"db": 2}, source_pools={"a": "db", "b": "db"})
    assert policy.choose_task_pool(op=op_single, tuning=tuning) == "db"

    tuning = AdaptiveTuning(pools={"db": 2, "api": 2}, source_pools={"a": "db", "b": "api"})
    assert policy.choose_task_pool(op=op_multi, tuning=tuning) == "default"


def test_adaptive_scheduler_enforces_pool_limits() -> None:
    source_a = _make_source("s1")
    source_b = _make_source("s2")
    source_c = _make_source("s3")

    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    op_c = _make_loadref_op(field_key="c", to_source=source_c, lookup_steps=(LookupStepIr(from_field="id", to_source=source_c),))

    plan = ExecutionPlan(operators=(op_a, op_b, op_c))
    tuning = AdaptiveTuning(pools={"db": 2}, source_pools={"s1": "db", "s2": "db", "s3": "db"})

    started = {"a": threading.Event(), "b": threading.Event(), "c": threading.Event()}
    finish = {"a": threading.Event(), "b": threading.Event(), "c": threading.Event()}

    current = {"n": 0, "max": 0}
    lock = threading.Lock()

    class _BlockingLoadRefExecutor:
        def __init__(self, shared_started, shared_finish, shared_current, shared_lock) -> None:  # type: ignore[no-untyped-def]
            self._started = shared_started
            self._finish = shared_finish
            self._current = shared_current
            self._lock = shared_lock

        def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
            op = cast("LoadRefOperatorIr", operator)  # pragma: allow-cast test executor typed narrowing
            with self._lock:
                self._current["n"] += 1
                self._current["max"] = max(self._current["max"], self._current["n"])
            self._started[op.field_key].set()
            if not self._finish[op.field_key].wait(timeout=1.0):
                raise RuntimeError("timeout waiting for finish")
            with self._lock:
                self._current["n"] -= 1
            _ = context
            _ = batch_row_nth
            _ = runtime

    overrides = PipelineOverrides(
        adaptive_tuning=tuning,
        adaptive_loadref_executor_factory=lambda: _BlockingLoadRefExecutor(started, finish, current, lock),
    )
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as pool:
        t = threading.Thread(
            target=lambda: scheduler.execute_segment(
                [op_a, op_b, op_c],
                context=BatchContext(),
                batch_row_nth=[0],
                runtime=runtime,
                pool=pool,
                max_workers=3,
                required_fields=None,
                after_operator=None,
            ),
            daemon=True,
        )
        t.start()

        assert started["a"].wait(timeout=1.0)
        assert started["b"].wait(timeout=1.0)
        assert started["c"].wait(timeout=0.3) is False

        finish["a"].set()
        assert started["c"].wait(timeout=1.0)

        finish["b"].set()
        finish["c"].set()
        t.join(timeout=5.0)
        assert not t.is_alive()

    assert current["max"] == 2


def test_adaptive_scheduler_threshold_lookup_keys_falls_back_to_serial() -> None:
    source_a = _make_source("s1")
    source_b = _make_source("s2")

    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))

    plan = ExecutionPlan(operators=(op_a, op_b))
    tuning = AdaptiveTuning(min_lookup_keys_per_task=3, min_parallel_tasks_per_layer=2)
    calls: List[str] = []
    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_tuning=tuning, adaptive_loadref_executor_factory=lambda: RecordingLoadRefExecutor(calls)),
    )
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    ctx = BatchContext()
    ctx.set_field_value("id", 0, 1)
    ctx.set_field_value("id", 1, 2)

    scheduler.execute_segment(
        [op_a, op_b],
        context=ctx,
        batch_row_nth=[0, 1],
        runtime=runtime,
        pool=object(),
        max_workers=4,
        required_fields=None,
        after_operator=None,
    )

    assert calls == ["a", "b"]


def test_adaptive_scheduler_policy_override_forces_serial() -> None:
    class _ForceSerialPolicy(AdaptivePolicy):
        def decide_layer_parallelism(  # type: ignore[override]
            self,
            layer_ops,
            *,
            tuning,
            runtime,
            pool_is_available,
            resolved_max_workers,
            layer_lookup_keys,
        ) -> AdaptiveLayerDecision:
            _ = layer_ops
            _ = tuning
            _ = runtime
            _ = pool_is_available
            _ = resolved_max_workers
            _ = layer_lookup_keys
            return AdaptiveLayerDecision(False, reason="forced_serial")

    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_a, op_b))

    calls: List[str] = []
    overrides = PipelineOverrides(
        adaptive_policy=_ForceSerialPolicy(),
        adaptive_loadref_executor_factory=lambda: RecordingLoadRefExecutor(calls),
    )
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    scheduler.execute_segment(
        [op_a, op_b],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=object(),
        max_workers=4,
        required_fields=None,
        after_operator=None,
    )

    assert calls == ["a", "b"]


def test_adaptive_scheduler_unknown_pool_from_policy_raises() -> None:
    class _BadPoolPolicy(AdaptivePolicy):
        def choose_task_pool(self, *, op, tuning):  # type: ignore[override]
            _ = op
            _ = tuning
            return "missing"

    source = _make_source("s1")
    op = _make_loadref_op(field_key="a", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source=source),))
    plan = ExecutionPlan(operators=(op,))

    overrides = PipelineOverrides(adaptive_policy=_BadPoolPolicy())
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=overrides)
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    with pytest.raises(ValueError, match="unknown pool"):
        scheduler.execute_segment(
            [op],
            context=BatchContext(),
            batch_row_nth=[0],
            runtime=runtime,
            pool=object(),
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )


def test_adaptive_scheduler_decision_events_are_wants_gated() -> None:
    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_a, op_b))

    tuning = AdaptiveTuning(pools={"db": 1}, source_pools={"s1": "db", "s2": "db"})
    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_tuning=tuning, adaptive_loadref_executor_factory=NoOpLoadRefExecutor),
    )

    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    scheduler.execute_segment(
        [op_a, op_b],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )

    perf = PerformanceObserver(
        config=PerformanceConfig(metrics={"duration"}, report_format="none", include_scheduler_decisions=True),
    )
    observer_manager = ObserverManager(observers=[perf])
    runtime = ExecutionRuntime(plan, HookManager(), observer_manager, main_source=None)

    scheduler.execute_segment(
        [op_a, op_b],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )

    assert perf.metrics.adaptive_scheduler is not None


def test_adaptive_scheduler_decision_events_reach_hooks_on_event() -> None:
    class _RecordingHook(BaseHook):
        def __init__(self) -> None:
            self.event_types = {EVENT_ADAPTIVE_SCHEDULER_DECISION}
            self.events = []

        def on_event(self, event):  # type: ignore[no-untyped-def]
            self.events.append(event)

    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_a, op_b))

    tuning = AdaptiveTuning(pools={"db": 1}, source_pools={"s1": "db", "s2": "db"})
    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_tuning=tuning, adaptive_loadref_executor_factory=NoOpLoadRefExecutor),
    )

    hook = _RecordingHook()
    hook_manager = HookManager()
    hook_manager.register(hook)
    runtime = ExecutionRuntime(plan, hook_manager, ObserverManager(), main_source=None)

    assert runtime.instrumentation.wants(EVENT_ADAPTIVE_SCHEDULER_DECISION) is True

    scheduler.execute_segment(
        [op_a, op_b],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )

    assert any(event.event_type == EVENT_ADAPTIVE_SCHEDULER_DECISION for event in hook.events)


def test_adaptive_scheduler_emits_pool_wait_stats_when_subscribed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    source_a = _make_source("s1")
    source_b = _make_source("s2")
    source_c = _make_source("s3")

    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    op_c = _make_loadref_op(field_key="c", to_source=source_c, lookup_steps=(LookupStepIr(from_field="id", to_source=source_c),))

    plan = ExecutionPlan(operators=(op_a, op_b, op_c))
    tuning = AdaptiveTuning(pools={"db": 2}, source_pools={"s1": "db", "s2": "db", "s3": "db"})

    started = {"a": threading.Event(), "b": threading.Event(), "c": threading.Event()}
    finish = threading.Event()
    pool_blocked = threading.Event()

    import scalim.execution.adaptive.submission_unit as submission_unit_module

    class _SignalingBoundedSemaphore:
        def __init__(self, value=1):  # type: ignore[no-untyped-def]
            self._initial = int(value)
            self._value = int(value)
            self._cond = threading.Condition()

        def acquire(self, blocking=True, timeout=None):  # type: ignore[no-untyped-def]
            _ = blocking
            _ = timeout
            with self._cond:
                while self._value <= 0:
                    pool_blocked.set()
                    self._cond.wait()
                self._value -= 1
                return True

        def release(self):  # type: ignore[no-untyped-def]
            with self._cond:
                if self._value >= self._initial:
                    raise ValueError("BoundedSemaphore released too many times")
                self._value += 1
                self._cond.notify()

    monkeypatch.setattr(submission_unit_module.threading, "BoundedSemaphore", _SignalingBoundedSemaphore, raising=True)

    class _BlockingLoadRefExecutor:
        def __init__(self, shared_started, shared_finish) -> None:  # type: ignore[no-untyped-def]
            self._started = shared_started
            self._finish = shared_finish

        def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
            op = cast("LoadRefOperatorIr", operator)  # pragma: allow-cast test executor typed narrowing
            self._started[op.field_key].set()
            if not self._finish.wait(timeout=1.0):
                raise RuntimeError("timeout waiting for finish")
            _ = context
            _ = batch_row_nth
            _ = runtime

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(
            adaptive_tuning=tuning,
            adaptive_loadref_executor_factory=lambda: _BlockingLoadRefExecutor(started, finish),
        ),
    )

    perf = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none", include_scheduler_decisions=True))
    observer_manager = ObserverManager(observers=[perf])
    runtime = ExecutionRuntime(plan, HookManager(), observer_manager, main_source=None, parallel_mode="adaptive", max_workers=3)
    runtime.batch_num = 1

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as pool:
        t = threading.Thread(
            target=lambda: scheduler.execute_segment(
                [op_a, op_b, op_c],
                context=BatchContext(),
                batch_row_nth=[0],
                runtime=runtime,
                pool=pool,
                max_workers=3,
                required_fields=None,
                after_operator=None,
            ),
            daemon=True,
        )
        t.start()
        assert started["a"].wait(timeout=1.0)
        assert started["b"].wait(timeout=1.0)
        assert pool_blocked.wait(timeout=1.0)
        assert started["c"].is_set() is False
        finish.set()
        t.join(timeout=1.0)
        assert not t.is_alive()

    scheduler_metrics = perf.metrics.adaptive_scheduler
    assert scheduler_metrics is not None
    assert scheduler_metrics.pool_limits.get("db") == 2


def test_estimate_first_step_lookup_key_count_handles_unhashable_values() -> None:
    source = _make_source("s1")
    op_single = _make_loadref_op(field_key="a", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source=source),))
    op_multi = _make_loadref_op(field_key="m", to_source=source, lookup_steps=(LookupStepIr(from_field=("a", "b"), to_source=source),))
    plan = ExecutionPlan(operators=(op_single, op_multi))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())

    ctx = BatchContext()
    ctx.set_field_value("id", 0, [1])  # unhashable
    assert scheduler._estimate_first_step_lookup_key_count(op_single, context=ctx, batch_row_nth=[0]) == 0  # noqa: SLF001

    ctx = BatchContext()
    ctx.set_field_value("a", 0, [1])  # unhashable
    ctx.set_field_value("b", 0, 2)
    assert scheduler._estimate_first_step_lookup_key_count(op_multi, context=ctx, batch_row_nth=[0]) == 0  # noqa: SLF001


def test_estimate_first_step_lookup_key_count_handles_empty_steps_and_missing_values() -> None:
    source = _make_source("s1")
    op_empty = _make_loadref_op(field_key="empty", to_source=source, lookup_steps=())
    op_single = _make_loadref_op(field_key="a", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source=source),))
    op_multi = _make_loadref_op(field_key="m", to_source=source, lookup_steps=(LookupStepIr(from_field=("a", "b"), to_source=source),))
    plan = ExecutionPlan(operators=(op_empty, op_single, op_multi))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())

    ctx = BatchContext()
    assert scheduler._estimate_first_step_lookup_key_count(op_empty, context=ctx, batch_row_nth=[0]) == 0  # noqa: SLF001

    ctx = BatchContext()
    ctx.set_field_value("id", 1, 1)
    assert scheduler._estimate_first_step_lookup_key_count(op_single, context=ctx, batch_row_nth=[0, 1]) == 1  # noqa: SLF001

    ctx = BatchContext()
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("a", 1, 1)
    ctx.set_field_value("b", 1, 2)
    assert scheduler._estimate_first_step_lookup_key_count(op_multi, context=ctx, batch_row_nth=[0, 1]) == 1  # noqa: SLF001


def test_adaptive_scheduler_submit_task_failure_releases_tokens_and_propagates() -> None:
    class _RaisingExecutor:
        def submit(self, _fn, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("submit boom")

    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_a, op_b))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    with pytest.raises(RuntimeError, match="submit boom"):
        scheduler.execute_segment(
            [op_a, op_b],
            context=BatchContext(),
            batch_row_nth=[0],
            runtime=runtime,
            pool=_RaisingExecutor(),
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )


def test_commit_layer_results_skips_field_keys_in_commit_loop() -> None:
    from scalim.execution.adaptive.loadref_scheduler import _AdaptiveTaskResult  # noqa: SLF001

    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_skip = _make_loadref_op(field_key="skip", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_exec = _make_loadref_op(field_key="exec", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_skip, op_exec))
    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(), main_source=None)

    ctx = BatchContext()
    results_by_key = {
        ("task", 2): _AdaptiveTaskResult(
            overlay={"exec": {0: 123}},
            hook_events=[],
            observer_events=[],
            relation_key=(),
            group_enabled=False,
        )
    }
    op_task_key = {"skip": ("task", 1), "exec": ("task", 2)}
    after_calls: List[str] = []

    scheduler._commit_layer_results(  # noqa: SLF001
        [op_skip, op_exec],
        skipped_field_keys={"skip"},
        op_task_key=op_task_key,
        results_by_key=results_by_key,
        context=ctx,
        runtime=runtime,
        committed_relation_keys=set(),
        after_operator=lambda op: after_calls.append(op.field_key),
    )

    assert ctx.get_field_value("exec", 0) == 123
    assert after_calls == ["exec"]


def test_adaptive_scheduler_emits_serial_decisions_when_subscribed() -> None:
    from scalim.spec.ir.binding import BindingIr
    from scalim.spec.ir.sources import MainSourceIr

    source = _make_source("s1")
    rows_binding = BindingIr(key_field="id", params_builder=lambda _ctx: ((), {}), mode="rows")
    op_rows = _make_loadref_op(
        field_key="rows", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source=source, bind=rows_binding),)
    )
    op_keys = _make_loadref_op(field_key="keys", to_source=source, lookup_steps=(LookupStepIr(from_field="id", to_source=source),))
    plan = ExecutionPlan(operators=(op_rows, op_keys))

    perf = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none", include_scheduler_decisions=True))
    runtime = ExecutionRuntime(
        plan, HookManager(), ObserverManager(observers=[perf]), main_source=MainSourceIr(source_id="main", loader=lambda: [])
    )
    runtime.batch_num = 1

    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_loadref_executor_factory=NoOpLoadRefExecutor),
    )
    scheduler.execute_segment(
        [op_rows, op_keys],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )

    assert perf.metrics.adaptive_scheduler is not None
    assert perf.metrics.adaptive_scheduler.serial_reasons.get("rows_binding_barrier") == 1

    # No pool branch.
    scheduler.execute_segment(
        [op_keys],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=None,
        max_workers=2,
        required_fields=None,
        after_operator=None,
    )
    assert perf.metrics.adaptive_scheduler.serial_reasons.get("no_pool") == 1

    # Single worker branch.
    scheduler.execute_segment(
        [op_keys],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=1,
        required_fields=None,
        after_operator=None,
    )
    assert perf.metrics.adaptive_scheduler.serial_reasons.get("single_worker") == 1


def test_adaptive_scheduler_emits_threshold_serial_reason_when_subscribed() -> None:
    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a, lookup_steps=(LookupStepIr(from_field="id", to_source=source_a),))
    op_b = _make_loadref_op(field_key="b", to_source=source_b, lookup_steps=(LookupStepIr(from_field="id", to_source=source_b),))
    plan = ExecutionPlan(operators=(op_a, op_b))

    perf = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none", include_scheduler_decisions=True))
    runtime = ExecutionRuntime(plan, HookManager(), ObserverManager(observers=[perf]), main_source=None)
    runtime.batch_num = 1

    tuning = AdaptiveTuning(min_parallel_tasks_per_layer=3)
    scheduler = AdaptiveLoadRefScheduler(
        plan,
        overrides=PipelineOverrides(adaptive_tuning=tuning, adaptive_loadref_executor_factory=NoOpLoadRefExecutor),
    )
    scheduler.execute_segment(
        [op_a, op_b],
        context=BatchContext(),
        batch_row_nth=[0],
        runtime=runtime,
        pool=InlineExecutor(),
        max_workers=4,
        required_fields=None,
        after_operator=None,
    )

    assert perf.metrics.adaptive_scheduler is not None
    assert perf.metrics.adaptive_scheduler.serial_reasons.get("below_min_parallel_tasks") == 1
