from concurrent.futures import Future
import threading

import pytest

from scalim.execution.adaptive.errors import ScalimAdaptiveTaskTimeoutError
from scalim.execution.adaptive.submission_unit import run_tasks_in_pool
from scalim.execution.adaptive.strategy_unit import TaskSpec
from scalim.planning.operators import LoadRefOperatorIr
from tests.support.testing_utils import CI_TIMEOUT_S, event_wait, join_or_fail


def test_run_tasks_in_pool_rejects_invalid_timeout_seconds_types_and_values() -> None:
    op = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type="load_ref",
        source_id="s1",
        field_key="a",
        lookup_steps=(),
    )
    spec = TaskSpec(op=op, relation_key=(), group_enabled=False, pool_name="p0")
    task_key = ("task", 1)

    def _submit_task(_spec: TaskSpec) -> "Future[int]":
        fut: "Future[int]" = Future()
        fut.set_result(1)
        return fut

    with pytest.raises(TypeError, match=r"timeout_seconds must be a float"):
        _ = run_tasks_in_pool(
            (task_key,),
            {task_key: spec},
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
            timeout_seconds=True,  # type: ignore[arg-type] contract boundary
        )

    with pytest.raises(ValueError, match=r"timeout_seconds must be finite"):
        _ = run_tasks_in_pool(
            (task_key,),
            {task_key: spec},
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
            timeout_seconds=float("inf"),
        )


def test_run_tasks_in_pool_collect_stats_zero_wait_does_not_increment_wait_count(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.adaptive import submission_unit as sub_mod

    monkeypatch.setattr(sub_mod.time, "perf_counter", lambda: 0.0)

    op = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type="load_ref",
        source_id="s1",
        field_key="a",
        lookup_steps=(),
    )
    spec = TaskSpec(op=op, relation_key=(), group_enabled=False, pool_name="p0")
    task_key = ("task", 1)

    def _submit_task(_spec: TaskSpec) -> "Future[int]":
        fut: "Future[int]" = Future()
        fut.set_result(123)
        return fut

    results_by_key, layer_stats = run_tasks_in_pool(
        (task_key,),
        {task_key: spec},
        max_workers=1,
        submit_task=_submit_task,
        collect_stats=True,
        resolve_pool_limit=lambda _pool_name, _resolved: 1,
    )
    assert results_by_key[task_key] == 123
    assert layer_stats is not None
    assert layer_stats.pool_wait["p0"].wait_count == 0


def test_run_tasks_in_pool_collect_stats_zero_wait_after_saturation_does_not_increment_wait_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scalim.execution.adaptive import submission_unit as sub_mod

    wait_started = threading.Event()
    call_count = {"n": 0}

    def _fake_perf_counter() -> float:
        call_count["n"] += 1
        if call_count["n"] == 1:
            wait_started.set()
        return 0.0

    monkeypatch.setattr(sub_mod.time, "perf_counter", _fake_perf_counter)

    op_a1 = LoadRefOperatorIr(
        operator_id="load_ref_a1",
        operator_type="load_ref",
        source_id="s1",
        field_key="a1",
        lookup_steps=(),
    )
    op_a2 = LoadRefOperatorIr(
        operator_id="load_ref_a2",
        operator_type="load_ref",
        source_id="s1",
        field_key="a2",
        lookup_steps=(),
    )

    task_a1 = ("task", "a1")
    task_a2 = ("task", "a2")

    specs = {
        task_a1: TaskSpec(op=op_a1, relation_key=(), group_enabled=False, pool_name="p0"),
        task_a2: TaskSpec(op=op_a2, relation_key=(), group_enabled=False, pool_name="p0"),
    }

    a1_future: "Future[int]" = Future()

    def _submit_task(spec: TaskSpec) -> "Future[int]":
        if spec.op.field_key == "a1":
            return a1_future
        fut: "Future[int]" = Future()
        fut.set_result(2)
        return fut

    def _release_a1_when_waiting() -> None:
        event_wait(wait_started, timeout_s=CI_TIMEOUT_S, label="adaptive pool wait started (zero wait)")
        a1_future.set_result(1)

    releaser = threading.Thread(target=_release_a1_when_waiting, name="test_run_tasks_in_pool_collect_stats_zero_wait_releaser")
    releaser.daemon = True
    releaser.start()
    try:
        results_by_key, layer_stats = run_tasks_in_pool(
            (task_a1, task_a2),
            specs,
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=True,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
        )
    finally:
        join_or_fail(releaser, timeout_s=CI_TIMEOUT_S, label="adaptive pool wait releaser (zero wait)")

    assert results_by_key[task_a1] == 1
    assert results_by_key[task_a2] == 2
    assert layer_stats is not None
    assert layer_stats.pool_wait["p0"].wait_count == 0


def test_run_tasks_in_pool_collect_stats_increments_wait_count_when_pool_was_saturated(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.adaptive import submission_unit as sub_mod

    wait_started = threading.Event()
    call_count = {"n": 0}

    def _fake_perf_counter() -> float:
        call_count["n"] += 1
        if call_count["n"] == 1:
            wait_started.set()
            return 0.0
        return 0.1

    monkeypatch.setattr(sub_mod.time, "perf_counter", _fake_perf_counter)

    op_a1 = LoadRefOperatorIr(
        operator_id="load_ref_a1",
        operator_type="load_ref",
        source_id="s1",
        field_key="a1",
        lookup_steps=(),
    )
    op_a2 = LoadRefOperatorIr(
        operator_id="load_ref_a2",
        operator_type="load_ref",
        source_id="s1",
        field_key="a2",
        lookup_steps=(),
    )

    task_a1 = ("task", "a1")
    task_a2 = ("task", "a2")

    specs = {
        task_a1: TaskSpec(op=op_a1, relation_key=(), group_enabled=False, pool_name="p0"),
        task_a2: TaskSpec(op=op_a2, relation_key=(), group_enabled=False, pool_name="p0"),
    }

    a1_future: "Future[int]" = Future()

    def _submit_task(spec: TaskSpec) -> "Future[int]":
        if spec.op.field_key == "a1":
            return a1_future
        fut: "Future[int]" = Future()
        fut.set_result(2)
        return fut

    def _release_a1_when_waiting() -> None:
        event_wait(wait_started, timeout_s=CI_TIMEOUT_S, label="adaptive pool wait started")
        a1_future.set_result(1)

    releaser = threading.Thread(target=_release_a1_when_waiting, name="test_run_tasks_in_pool_collect_stats_releaser")
    releaser.daemon = True
    releaser.start()
    try:
        results_by_key, layer_stats = run_tasks_in_pool(
            (task_a1, task_a2),
            specs,
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=True,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
        )
    finally:
        join_or_fail(releaser, timeout_s=CI_TIMEOUT_S, label="adaptive pool wait releaser")

    assert results_by_key[task_a1] == 1
    assert results_by_key[task_a2] == 2
    assert layer_stats is not None
    assert layer_stats.pool_wait["p0"].wait_count == 1


def test_run_tasks_in_pool_timeout_fails_fast_with_diagnostics() -> None:
    op = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type="load_ref",
        source_id="s1",
        field_key="a",
        lookup_steps=(),
    )
    spec = TaskSpec(op=op, relation_key=(), group_enabled=False, pool_name="p0")
    task_key = ("task", 1)

    unblock = threading.Event()
    worker_done = threading.Event()

    def _submit_task(_spec: TaskSpec) -> "Future[int]":
        fut: "Future[int]" = Future()

        def _worker() -> None:
            unblock.wait()
            if fut.cancelled() or fut.done():
                worker_done.set()
                return
            fut.set_result(123)
            worker_done.set()

        thread = threading.Thread(target=_worker, name="test_run_tasks_in_pool_timeout_worker")
        thread.daemon = True
        thread.start()
        return fut

    with pytest.raises(ScalimAdaptiveTaskTimeoutError) as excinfo:
        _ = run_tasks_in_pool(
            (task_key,),
            {task_key: spec},
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
            timeout_seconds=0.2,
        )
    text = str(excinfo.value)
    assert "pending_task_keys=[" in text
    assert "pending_field_keys=[" in text
    assert "('task', 1)" in text
    assert "a" in text

    unblock.set()
    event_wait(worker_done, label="adaptive submission timeout worker_done")


def test_run_tasks_in_pool_releases_pool_token_when_global_token_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.adaptive import submission_unit as sub_mod

    op_a = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type="load_ref",
        source_id="s1",
        field_key="a",
        lookup_steps=(),
    )
    op_b = LoadRefOperatorIr(
        operator_id="load_ref_b",
        operator_type="load_ref",
        source_id="s2",
        field_key="b",
        lookup_steps=(),
    )

    task_a = ("task", "a")
    task_b = ("task", "b")
    specs = {
        task_a: TaskSpec(op=op_a, relation_key=(), group_enabled=False, pool_name="pA"),
        task_b: TaskSpec(op=op_b, relation_key=(), group_enabled=False, pool_name="pB"),
    }

    a_future: "Future[int]" = Future()
    entered_wait = threading.Event()
    original_wait = sub_mod.wait

    def _wait_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
        entered_wait.set()
        return original_wait(*args, **kwargs)

    monkeypatch.setattr(sub_mod, "wait", _wait_wrapper)

    def _submit_task(spec: TaskSpec) -> "Future[int]":
        if spec.op.field_key == "a":
            return a_future
        fut: "Future[int]" = Future()
        fut.set_result(2)
        return fut

    def _release_a_after_global_block() -> None:
        event_wait(entered_wait, timeout_s=CI_TIMEOUT_S, label="adaptive global semaphore wait entered")
        a_future.set_result(1)

    releaser = threading.Thread(target=_release_a_after_global_block, name="test_run_tasks_in_pool_global_token_releaser")
    releaser.daemon = True
    releaser.start()
    try:
        results_by_key, _stats = run_tasks_in_pool(
            (task_a, task_b),
            specs,
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
        )
    finally:
        join_or_fail(releaser, timeout_s=CI_TIMEOUT_S, label="adaptive global token releaser")

    assert results_by_key[task_a] == 1
    assert results_by_key[task_b] == 2


def test_run_tasks_in_pool_no_in_flight_continues_without_hanging(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.adaptive import submission_unit as sub_mod

    original_acquire = sub_mod.threading.BoundedSemaphore.acquire
    call_count = {"n": 0}

    def _acquire_once(self, blocking: bool = True, timeout=None):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] == 1:
            return False
        return original_acquire(self, blocking=blocking, timeout=timeout)

    monkeypatch.setattr(sub_mod.threading.BoundedSemaphore, "acquire", _acquire_once)

    op = LoadRefOperatorIr(
        operator_id="load_ref_a",
        operator_type="load_ref",
        source_id="s1",
        field_key="a",
        lookup_steps=(),
    )
    spec = TaskSpec(op=op, relation_key=(), group_enabled=False, pool_name="p0")
    task_key = ("task", 1)

    def _submit_task(_spec: TaskSpec) -> "Future[int]":
        fut: "Future[int]" = Future()
        fut.set_result(123)
        return fut

    results_by_key, _stats = run_tasks_in_pool(
        (task_key,),
        {task_key: spec},
        max_workers=1,
        submit_task=_submit_task,
        collect_stats=False,
        resolve_pool_limit=lambda _pool_name, _resolved: 1,
    )
    assert results_by_key[task_key] == 123


def test_run_tasks_in_pool_timeout_triggers_pending_loop_wait_path() -> None:
    op_a1 = LoadRefOperatorIr(
        operator_id="load_ref_a1",
        operator_type="load_ref",
        source_id="s1",
        field_key="a1",
        lookup_steps=(),
    )
    op_a2 = LoadRefOperatorIr(
        operator_id="load_ref_a2",
        operator_type="load_ref",
        source_id="s1",
        field_key="a2",
        lookup_steps=(),
    )

    task_a1 = ("task", "a1")
    task_a2 = ("task", "a2")

    specs = {
        task_a1: TaskSpec(op=op_a1, relation_key=(), group_enabled=False, pool_name="p0"),
        task_a2: TaskSpec(op=op_a2, relation_key=(), group_enabled=False, pool_name="p0"),
    }

    a1_future: "Future[int]" = Future()

    def _submit_task(spec: TaskSpec) -> "Future[int]":
        if spec.op.field_key == "a1":
            return a1_future
        fut: "Future[int]" = Future()
        fut.set_result(2)
        return fut

    with pytest.raises(ScalimAdaptiveTaskTimeoutError) as excinfo:
        _ = run_tasks_in_pool(
            (task_a1, task_a2),
            specs,
            max_workers=1,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda _pool_name, _resolved: 1,
            timeout_seconds=0.05,
        )
    text = str(excinfo.value)
    assert "('task', 'a1')" in text
    assert "('task', 'a2')" in text
    assert "a1" in text
    assert "a2" in text


def test_run_tasks_in_pool_two_pools_saturation_does_not_block_other_pool_submission() -> None:
    op_a1 = LoadRefOperatorIr(
        operator_id="load_ref_a1",
        operator_type="load_ref",
        source_id="s1",
        field_key="a1",
        lookup_steps=(),
    )
    op_b1 = LoadRefOperatorIr(
        operator_id="load_ref_b1",
        operator_type="load_ref",
        source_id="s2",
        field_key="b1",
        lookup_steps=(),
    )
    op_a2 = LoadRefOperatorIr(
        operator_id="load_ref_a2",
        operator_type="load_ref",
        source_id="s1",
        field_key="a2",
        lookup_steps=(),
    )
    op_b2 = LoadRefOperatorIr(
        operator_id="load_ref_b2",
        operator_type="load_ref",
        source_id="s2",
        field_key="b2",
        lookup_steps=(),
    )

    task_a1 = ("task", "a1")
    task_b1 = ("task", "b1")
    task_a2 = ("task", "a2")
    task_b2 = ("task", "b2")

    specs = {
        task_a1: TaskSpec(op=op_a1, relation_key=(("a1",),), group_enabled=False, pool_name="pA"),
        task_b1: TaskSpec(op=op_b1, relation_key=(("b1",),), group_enabled=False, pool_name="pB"),
        task_a2: TaskSpec(op=op_a2, relation_key=(("a2",),), group_enabled=False, pool_name="pA"),
        task_b2: TaskSpec(op=op_b2, relation_key=(("b2",),), group_enabled=False, pool_name="pB"),
    }

    a1_future: "Future[int]" = Future()
    b2_submitted = threading.Event()

    submitted: list = []

    def _submit_task(spec: TaskSpec) -> "Future[int]":
        submitted.append(spec.op.field_key)
        if spec.op.field_key == "a1":
            return a1_future
        fut: "Future[int]" = Future()
        fut.set_result(1)
        if spec.op.field_key == "b2":
            b2_submitted.set()
        return fut

    def _run() -> None:
        run_tasks_in_pool(
            (task_a1, task_b1, task_a2, task_b2),
            specs,
            max_workers=2,
            submit_task=_submit_task,
            collect_stats=False,
            resolve_pool_limit=lambda pool_name, _resolved: 1,
        )

    thread = threading.Thread(target=_run, name="test_run_tasks_in_pool_two_pools")
    thread.daemon = True
    thread.start()
    try:
        event_wait(b2_submitted, timeout_s=CI_TIMEOUT_S, label="adaptive submission b2_submitted")
        assert a1_future.done() is False
    finally:
        if not a1_future.done():
            a1_future.set_result(1)

    join_or_fail(thread, timeout_s=CI_TIMEOUT_S, label="adaptive submission runner")
    assert "b2" in submitted
