from concurrent.futures import Future

import pytest

from scalim.execution.adaptive.submission_unit import run_tasks_in_pool
from scalim.execution.adaptive.strategy_unit import TaskSpec
from scalim.planning.operators import LoadRefOperatorIr


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
