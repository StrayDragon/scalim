import threading
from typing import List

from scalim.events import EventType
from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import DemandIr
from scalim.spec.ir import MainSourceIr, RuntimeHandleIdIr

from tests.support.testing_utils import CI_TIMEOUT_S, NEGATIVE_TIMEOUT_S, barrier_wait, event_wait, join_or_fail

_TIMEOUT_S = CI_TIMEOUT_S


def test_scalim_engine_run_is_serialized_per_instance() -> None:
    runtime_bindings = RuntimeBindings()
    demand = DemandIr(
        sources={},
        fields={},
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr("main_source:main")),
    )
    plan = ExecutionPlan(target_fields=["x"])
    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1)

    run1_started = threading.Event()
    run1_can_continue = threading.Event()
    run2_started = threading.Event()
    run2_thread_started = threading.Event()

    def _rows1():  # type: ignore[no-untyped-def]
        run1_started.set()
        event_wait(run1_can_continue, timeout_s=_TIMEOUT_S, label="run1_can_continue")
        yield {"x": 1}

    def _rows2():  # type: ignore[no-untyped-def]
        run2_started.set()
        yield {"x": 2}

    errors: List[BaseException] = []

    def _run_rows(rows):  # type: ignore[no-untyped-def]
        try:
            _ = engine.run(main_rows=rows)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=lambda: _run_rows(_rows1()), daemon=True)
    t1.start()
    event_wait(run1_started, timeout_s=_TIMEOUT_S, label="run1_started")

    def _run_rows2() -> None:
        run2_thread_started.set()
        _run_rows(_rows2())

    t2 = threading.Thread(target=_run_rows2, daemon=True)
    t2.start()

    event_wait(run2_thread_started, timeout_s=_TIMEOUT_S, label="run2_thread_started")
    assert run2_started.wait(timeout=NEGATIVE_TIMEOUT_S) is False

    run1_can_continue.set()
    join_or_fail(t1, timeout_s=_TIMEOUT_S, label="engine.run.t1")
    join_or_fail(t2, timeout_s=_TIMEOUT_S, label="engine.run.t2")
    assert not errors
    assert run2_started.is_set() is True


def test_observer_manager_capture_drain_and_emit_are_thread_safe() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=None)

    start = threading.Barrier(2)
    done = threading.Event()
    errors: List[BaseException] = []

    def _emit():  # type: ignore[no-untyped-def]
        try:
            barrier_wait(start, label="observer_manager._emit.start")
            for i in range(2000):
                manager.emit_event("x", payload=i)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            done.set()

    def _drain():  # type: ignore[no-untyped-def]
        try:
            barrier_wait(start, label="observer_manager._drain.start")
            while not done.is_set():
                _ = manager.drain_events()
            _ = manager.drain_events()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_emit, daemon=True)
    t2 = threading.Thread(target=_drain, daemon=True)
    t1.start()
    t2.start()
    join_or_fail(t1, timeout_s=CI_TIMEOUT_S, label="observer_manager._emit")
    join_or_fail(t2, timeout_s=CI_TIMEOUT_S, label="observer_manager._drain")
    assert not errors


def test_hook_manager_register_unreg_while_emitting_is_thread_safe() -> None:
    manager = HookManager()

    class _Hook(BaseHook):
        def __init__(self) -> None:
            self.calls = 0

        def on_pipeline_start(self, event) -> None:  # type: ignore[override]
            _ = event
            self.calls += 1

    hook = _Hook()

    start = threading.Barrier(2)
    done = threading.Event()
    errors: List[BaseException] = []

    def _emit():  # type: ignore[no-untyped-def]
        try:
            barrier_wait(start, label="hook_manager._emit.start")
            for _i in range(2000):
                manager.emit_typed(EventType.PIPELINE_START, payload=None)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            done.set()

    def _mutate():  # type: ignore[no-untyped-def]
        try:
            barrier_wait(start, label="hook_manager._mutate.start")
            while not done.is_set():
                manager.register(hook)
                _ = manager.unregister(hook)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_emit, daemon=True)
    t2 = threading.Thread(target=_mutate, daemon=True)
    t1.start()
    t2.start()
    join_or_fail(t1, timeout_s=CI_TIMEOUT_S, label="hook_manager._emit")
    join_or_fail(t2, timeout_s=CI_TIMEOUT_S, label="hook_manager._mutate")
    assert not errors
