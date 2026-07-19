# pragma: allow-c901-file plan: c60
import math
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, as_completed, wait
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Callable, Dict, List, Optional, Sequence, Tuple, TypeVar

from ...vendor.dataclassesx import dataclass
from .errors import ScalimAdaptiveTaskTimeoutError
from .strategy_unit import AdaptiveTaskKey, TaskSpec


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
    task_order: Sequence[AdaptiveTaskKey],
    task_specs: Dict[AdaptiveTaskKey, TaskSpec],
    *,
    max_workers: int,
    # `Python 3.6` 兼容性:`concurrent.futures.Future` 在运行时不可下标.
    submit_task: Callable[[TaskSpec], "Future[_TResult]"],
    collect_stats: bool,
    resolve_pool_limit: Callable[[str, int], int],
    timeout_seconds: Optional[float] = None,
) -> Tuple[Dict[AdaptiveTaskKey, _TResult], Optional[LayerScheduleStats]]:
    timeout_s = None
    if timeout_seconds is not None:
        if isinstance(timeout_seconds, bool):
            msg = "timeout_seconds must be a float seconds value or None"
            raise TypeError(msg)
        value = float(timeout_seconds)
        if not math.isfinite(value):
            msg = "timeout_seconds must be finite"
            raise ValueError(msg)
        if value > 0:
            timeout_s = value

    deadline: Optional[float] = None
    if timeout_s is not None:
        deadline = time.perf_counter() + float(timeout_s)

    def _remaining_timeout_seconds() -> Optional[float]:
        if deadline is None:
            return None
        return max(0.0, float(deadline) - time.perf_counter())

    def _raise_timeout(*, pending_task_keys: Sequence[AdaptiveTaskKey]) -> None:
        pending_field_keys: List[str] = []
        for task_key in pending_task_keys:
            spec = task_specs.get(task_key)
            if spec is None:  # pragma: no cover  # pragma: allow-no-cover defensive: unknown key
                continue
            pending_field_keys.append(str(spec.op.field_key))
        raise ScalimAdaptiveTaskTimeoutError(
            timeout_seconds=float(timeout_s or 0.0),
            pending_task_keys=tuple(pending_task_keys),
            pending_field_keys=tuple(pending_field_keys),
        )

    resolved_workers = max(1, int(max_workers))
    global_sem = threading.BoundedSemaphore(resolved_workers)

    pool_sems: Dict[str, threading.BoundedSemaphore] = {}
    pool_limits: Dict[str, int] = {}
    pool_wait: Dict[str, PoolWaitStats] = {}
    pool_wait_start: Dict[str, float] = {}
    for task_key in task_order:
        spec = task_specs[task_key]
        if spec.pool_name not in pool_sems:
            limit = max(1, int(resolve_pool_limit(spec.pool_name, resolved_workers)))
            pool_limits[spec.pool_name] = int(limit)
            pool_sems[spec.pool_name] = threading.BoundedSemaphore(limit)
            if collect_stats:
                pool_wait[spec.pool_name] = PoolWaitStats()

    futures: Dict[AdaptiveTaskKey, "Future[_TResult]"] = {}
    future_to_key: Dict["Future[_TResult]", AdaptiveTaskKey] = {}

    def _release_tokens(pool_name: str) -> None:
        pool_sems[pool_name].release()
        global_sem.release()

    pending: List[AdaptiveTaskKey] = list(task_order)
    while pending:
        submitted_any = False
        i = 0
        while i < len(pending):
            task_key = pending[i]
            spec = task_specs[task_key]
            pool_name = spec.pool_name
            pool_sem = pool_sems[pool_name]

            acquired_pool = pool_sem.acquire(blocking=False)
            if not acquired_pool:
                if collect_stats and pool_name not in pool_wait_start:
                    pool_wait_start[pool_name] = time.perf_counter()
                i += 1
                continue

            if collect_stats:
                start = pool_wait_start.pop(pool_name, None)
                if start is not None:
                    waited = max(0.0, time.perf_counter() - start)
                    stats = pool_wait[pool_name]
                    stats.wait_seconds_total += waited
                    stats.wait_seconds_max = max(stats.wait_seconds_max, waited)
                    if waited > _POOL_WAIT_EPSILON_SECONDS:
                        stats.wait_count += 1

            acquired_global = global_sem.acquire(blocking=False)
            if not acquired_global:
                pool_sem.release()
                i += 1
                continue

            try:
                fut = submit_task(spec)
            except Exception:
                _release_tokens(pool_name)
                raise

            futures[task_key] = fut
            future_to_key[fut] = task_key
            fut.add_done_callback(lambda _fut, pool_name=pool_name: _release_tokens(pool_name))

            _ = pending.pop(i)
            submitted_any = True

        if submitted_any:
            continue

        in_flight = [fut for fut in futures.values() if not fut.done()]
        if not in_flight:
            continue

        done, _not_done = wait(
            in_flight,
            timeout=_remaining_timeout_seconds(),
            return_when=FIRST_COMPLETED,
        )
        if not done:
            pending_task_keys: List[AdaptiveTaskKey] = []
            pending_task_keys.extend(pending)
            pending_task_keys.extend(task_key for task_key, fut in futures.items() if not fut.done())
            for fut in futures.values():
                _ = fut.cancel()
            _raise_timeout(pending_task_keys=pending_task_keys)

    results_by_key: Dict[AdaptiveTaskKey, _TResult] = {}
    try:
        remaining_timeout = _remaining_timeout_seconds()
        if remaining_timeout is None:
            iterator = as_completed(list(futures.values()))
        else:
            iterator = as_completed(list(futures.values()), timeout=remaining_timeout)
        for fut in iterator:
            done_key = future_to_key.get(fut)
            if done_key is None:  # pragma: no cover  # pragma: allow-no-cover defensive: unknown future key
                continue
            results_by_key[done_key] = fut.result()
    except FuturesTimeoutError:
        pending_task_keys = [task_key for task_key, fut in futures.items() if not fut.done()]
        for fut in futures.values():
            _ = fut.cancel()
        _raise_timeout(pending_task_keys=pending_task_keys)
    except Exception:
        for fut in futures.values():
            _ = fut.cancel()
        raise

    layer_stats = None
    if collect_stats:
        layer_stats = LayerScheduleStats(pool_limits=pool_limits, pool_wait=pool_wait)
    return results_by_key, layer_stats


__all__ = ("LayerScheduleStats", "PoolWaitStats", "run_tasks_in_pool")
