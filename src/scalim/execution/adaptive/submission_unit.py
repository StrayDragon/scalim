import threading
import time
from concurrent.futures import Future, as_completed
from typing import Callable, Dict, Optional, Sequence, Tuple, TypeVar

from ...vendor.dataclassesx import dataclass
from .strategy_unit import TaskSpec


@dataclass
class PoolWaitStats:
    wait_seconds_total: float = 0.0
    wait_seconds_max: float = 0.0
    wait_count: int = 0


@dataclass
class LayerScheduleStats:
    pool_limits: Dict[str, int]
    pool_wait: Dict[str, PoolWaitStats]


_POOL_WAIT_EPSILON_SECONDS = 0.000_001


_TResult = TypeVar("_TResult")


def run_tasks_in_pool(  # noqa: C901, PLR0912, PLR0915
    task_order: Sequence[Tuple[str, object]],
    task_specs: Dict[Tuple[str, object], TaskSpec],
    *,
    max_workers: int,
    # `Python 3.6` 兼容性:`concurrent.futures.Future` 在运行时不可下标.
    submit_task: Callable[[TaskSpec], "Future[_TResult]"],
    collect_stats: bool,
    resolve_pool_limit: Callable[[str, int], int],
) -> Tuple[Dict[Tuple[str, object], _TResult], Optional[LayerScheduleStats]]:
    resolved_workers = max(1, int(max_workers))
    global_sem = threading.BoundedSemaphore(resolved_workers)

    pool_sems: Dict[str, threading.BoundedSemaphore] = {}
    pool_limits: Dict[str, int] = {}
    pool_wait: Dict[str, PoolWaitStats] = {}
    for task_key in task_order:
        spec = task_specs[task_key]
        if spec.pool_name not in pool_sems:
            limit = max(1, int(resolve_pool_limit(spec.pool_name, resolved_workers)))
            pool_limits[spec.pool_name] = int(limit)
            pool_sems[spec.pool_name] = threading.BoundedSemaphore(limit)

    futures: Dict[Tuple[str, object], "Future[_TResult]"] = {}
    future_to_key: Dict["Future[_TResult]", Tuple[str, object]] = {}

    def _release_tokens(pool_name: str) -> None:
        pool_sems[pool_name].release()
        global_sem.release()

    for task_key in task_order:
        spec = task_specs[task_key]
        _ = global_sem.acquire()
        if collect_stats:
            wait_start = time.perf_counter()
            _ = pool_sems[spec.pool_name].acquire()
            waited = max(0.0, time.perf_counter() - wait_start)
            stats = pool_wait.get(spec.pool_name)
            if stats is None:
                stats = PoolWaitStats()
                pool_wait[spec.pool_name] = stats
            stats.wait_seconds_total += waited
            stats.wait_seconds_max = max(stats.wait_seconds_max, waited)
            if waited > _POOL_WAIT_EPSILON_SECONDS:
                stats.wait_count += 1
        else:
            _ = pool_sems[spec.pool_name].acquire()
        try:
            fut = submit_task(spec)
        except Exception:
            _release_tokens(spec.pool_name)
            raise

        futures[task_key] = fut
        future_to_key[fut] = task_key
        fut.add_done_callback(lambda _fut, pool_name=spec.pool_name: _release_tokens(pool_name))

    results_by_key: Dict[Tuple[str, object], _TResult] = {}
    try:
        for fut in as_completed(list(futures.values())):
            done_key = future_to_key.get(fut)
            if done_key is None:  # pragma: no cover  # pragma: allow-no-cover defensive: unknown future key
                continue
            results_by_key[done_key] = fut.result()
    except Exception:
        for fut in futures.values():
            _ = fut.cancel()
        raise

    layer_stats = None
    if collect_stats:
        layer_stats = LayerScheduleStats(pool_limits=pool_limits, pool_wait=pool_wait)
    return results_by_key, layer_stats


__all__ = ("LayerScheduleStats", "PoolWaitStats", "run_tasks_in_pool")
