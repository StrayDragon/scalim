from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import pytest

from scalim.events import EVENT_RELATION_LOOKUP, Event
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import FieldIr, KeyIr, LookupStepIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import LoaderIr


class _RecordingRelationLookupObserver(Observer):
    event_types: Optional[Set[str]] = {EVENT_RELATION_LOOKUP}

    def __init__(self) -> None:
        self.events: List[Event] = []

    def on_event(self, event: Event) -> None:
        self.events.append(event)


def _noop_loader(*_args: Any, **_kwargs: Any) -> Dict[Any, Any]:
    return {}


def _main_loader() -> List[Dict[str, Any]]:
    return []


def _make_source(source_id: str) -> SourceIr:
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="{}.loader".format(source_id))),
    )


def _make_loadref_op(*, field_key: str, to_source: SourceIr) -> LoadRefOperatorIr:
    return LoadRefOperatorIr(
        operator_id="load_ref_{}".format(field_key),
        operator_type=OperatorType.LOAD_REF.value,
        source_id=to_source.source_id,
        field_key=field_key,
        lookup_steps=(LookupStepIr(from_field="id", to_source=to_source),),
    )


def _build_plan(ops: Tuple[LoadRefOperatorIr, ...]) -> ExecutionPlan:
    field_specs = {}
    for op in ops:
        if not op.lookup_steps:
            continue
        field_specs[op.field_key] = FieldIr(field_id=op.field_key, name=op.field_key, source=op.lookup_steps[-1].to_source)
    return ExecutionPlan(
        operators=ops,
        field_specs=field_specs,
        key_fields=frozenset({"id"}),
        target_fields=sorted(field_specs.keys()),
    )


@pytest.mark.parametrize("key_normalization", ["force_str", "auto_str"])
def test_adaptive_per_task_runtime_inherits_key_normalization_and_observability_config(
    monkeypatch: Any,
    key_normalization: str,
) -> None:
    source_a = _make_source("s1")
    source_b = _make_source("s2")
    op_a = _make_loadref_op(field_key="a", to_source=source_a)
    op_b = _make_loadref_op(field_key="b", to_source=source_b)
    plan = _build_plan((op_a, op_b))
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))

    preloaded_cache = {
        "s1": {"1": {"a": "A"}},
        "s2": {"1": {"b": "B"}},
    }

    meta_defaults = {"test_meta": "ok"}

    # ---- seq baseline ----
    seq_observer = _RecordingRelationLookupObserver()
    seq_observer_manager = ObserverManager(
        observers=[seq_observer],
        enable_debugging=True,
        fallback_logger_enabled=True,
        run_id="run_seq",
        event_meta_defaults=meta_defaults,
    )
    seq_runtime = ExecutionRuntime(
        plan,
        HookManager(enable_debugging=True, fallback_logger_enabled=True),
        seq_observer_manager,
        main_source=main_source,
        sources={"s1": source_a, "s2": source_b},
        runtime_bindings=RuntimeBindings(main_source_loaders={"orders": _main_loader}),
        parallel_mode="seq",
        max_workers=0,
        key_normalization=key_normalization,  # type: ignore[arg-type]
    )
    seq_runtime.preloaded_cache = dict(preloaded_cache)
    seq_runtime.batch_num = 1

    seq_ctx = BatchContext()
    seq_ctx.set_field_value("id", 0, 1)
    exec_ = LoadRefOperatorExecutor()
    exec_.execute(op_a, seq_ctx, [0], seq_runtime)
    exec_.execute(op_b, seq_ctx, [0], seq_runtime)

    assert seq_ctx.get_field_value("a", 0) == "A"
    assert seq_ctx.get_field_value("b", 0) == "B"
    assert [e.payload.result for e in seq_observer.events] == ["hit", "hit"]
    assert all(e.meta and e.meta.get("test_meta") == "ok" for e in seq_observer.events)

    # ---- adaptive ----
    import scalim.execution.adaptive._internal.loadref_scheduler_execution as exec_mod

    seen: Dict[str, object] = {}

    real_hook_capture_manager = exec_mod.HookCaptureManager

    class _SpyHookCaptureManager(real_hook_capture_manager):  # type: ignore[misc, valid-type]
        def __init__(self, source: HookManager) -> None:
            seen["hook_source"] = source
            super().__init__(source)
            seen["hook_debug_mode"] = bool(self.debug_mode)
            seen["hook_fallback_logger_enabled"] = bool(self.fallback_logger_enabled)

    monkeypatch.setattr(exec_mod, "HookCaptureManager", _SpyHookCaptureManager)

    real_create_capture_manager = ObserverManager.create_capture_manager

    def _spy_create_capture_manager(self: ObserverManager) -> Any:
        capture = real_create_capture_manager(self)
        seen["observer_capture_manager"] = capture
        seen["observer_capture_debug_mode"] = bool(getattr(capture, "debug_mode", False))
        seen["observer_capture_fallback_logger_enabled"] = bool(getattr(capture, "fallback_logger_enabled", False))
        seen["observer_capture_run_id"] = str(getattr(capture, "run_id", ""))
        return capture

    monkeypatch.setattr(ObserverManager, "create_capture_manager", _spy_create_capture_manager)

    adaptive_observer = _RecordingRelationLookupObserver()
    adaptive_observer_manager = ObserverManager(
        observers=[adaptive_observer],
        enable_debugging=True,
        fallback_logger_enabled=True,
        run_id="run_adaptive",
        event_meta_defaults=meta_defaults,
    )
    adaptive_hook_manager = HookManager(enable_debugging=True, fallback_logger_enabled=True)
    adaptive_runtime = ExecutionRuntime(
        plan,
        adaptive_hook_manager,
        adaptive_observer_manager,
        main_source=main_source,
        sources={"s1": source_a, "s2": source_b},
        runtime_bindings=RuntimeBindings(main_source_loaders={"orders": _main_loader}),
        parallel_mode="adaptive",
        max_workers=2,
        key_normalization=key_normalization,  # type: ignore[arg-type]
    )
    adaptive_runtime.preloaded_cache = dict(preloaded_cache)
    adaptive_runtime.batch_num = 1

    adaptive_ctx = BatchContext()
    adaptive_ctx.set_field_value("id", 0, 1)

    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides(adaptive_min_parallel_tasks=1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        scheduler.execute_segment(
            [op_a, op_b],
            context=adaptive_ctx,
            batch_row_nth=[0],
            runtime=adaptive_runtime,
            pool=pool,
            max_workers=2,
            required_fields=None,
            after_operator=None,
        )

    assert adaptive_ctx.get_field_value("a", 0) == "A"
    assert adaptive_ctx.get_field_value("b", 0) == "B"

    events = adaptive_observer.events
    assert [e.payload.result for e in events] == ["hit", "hit"]
    assert all(e.meta and e.meta.get("test_meta") == "ok" for e in events)

    # per-task runtime MUST derive capture managers from the parent runtime and inherit toggles.
    assert seen.get("hook_source") is adaptive_hook_manager
    assert seen.get("hook_debug_mode") is True
    assert seen.get("hook_fallback_logger_enabled") is True

    assert seen.get("observer_capture_manager") is not None
    assert seen.get("observer_capture_debug_mode") is True
    assert seen.get("observer_capture_fallback_logger_enabled") is True
    assert seen.get("observer_capture_run_id") == "run_adaptive"
