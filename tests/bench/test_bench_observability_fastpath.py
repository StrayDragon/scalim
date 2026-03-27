import os
from typing import Callable, Dict

import pytest

from scalim_benchlib import BenchmarkRunner
from scalim._project_constants import ENV_BENCH_SCALE, ENV_BENCH_SCOPE
from scalim.events import EVENT_PIPELINE_START
from scalim.hooks import HookManager
from scalim.ob.hub import InstrumentationHub
from scalim.ob.manager import ObserverManager


def _bench_scale() -> str:
    return os.getenv(ENV_BENCH_SCALE, "small")


def _bench_scope() -> str:
    return os.getenv(ENV_BENCH_SCOPE, "observability-fastpath")


def _bench_iters() -> int:
    scale = _bench_scale()
    return {
        "small": 200_000,
        "medium": 500_000,
        "large": 1_000_000,
    }.get(scale, 200_000)


def _bench_info(scenario: str, iters: int) -> Dict[str, object]:
    return {
        "scenario": scenario,
        "scale": _bench_scale(),
        "scope": _bench_scope(),
        "iters": iters,
    }


def _make_runner(scenario: str, iters: int) -> Callable[[], int]:
    deps: Dict[str, object] = {}

    if scenario == "field_compute":
        hook_manager = HookManager(fallback_logger_enabled=False)
        observer_manager = ObserverManager(fallback_logger_enabled=False)

        def _run() -> int:
            for idx in range(iters):
                hook_manager.trigger_field_compute("f", idx, deps, idx)
                observer_manager.emit_field_compute("f", idx, deps, idx)
            return iters

        return _run

    if scenario == "loader_call_sample":
        result = list(range(1000))
        hook_manager = HookManager(
            fallback_logger_enabled=False,
            loader_result_policy="sample",
            loader_result_sample_size=5,
        )
        observer_manager = ObserverManager(
            fallback_logger_enabled=False,
            loader_result_policy="sample",
            loader_result_sample_size=5,
        )

        def _run() -> int:
            for _idx in range(iters):
                hook_manager.trigger_loader_call("loader", {"p": 1}, result, 0.1)
                observer_manager.emit_loader_call("loader", {"p": 1}, result, 0.1)
            return iters

        return _run

    if scenario == "row_write":
        hook_manager = HookManager(fallback_logger_enabled=False)
        observer_manager = ObserverManager(fallback_logger_enabled=False)

        def _run() -> int:
            for idx in range(iters):
                hook_manager.trigger_row_write(row_id=idx, field_count=3, batch_num=1, row_index=idx)
                observer_manager.emit_row_write(row_id=idx, field_count=3, batch_num=1, row_index=idx)
            return iters

        return _run

    if scenario == "hub_emit_lazy":
        hub = InstrumentationHub(
            hook_manager=HookManager(fallback_logger_enabled=False),
            observer_manager=ObserverManager(fallback_logger_enabled=False),
        )

        def _payload_factory() -> int:
            return 1

        def _run() -> int:
            for _idx in range(iters):
                _ = hub.emit_lazy(EVENT_PIPELINE_START, _payload_factory)
            return iters

        return _run

    raise ValueError("Unknown scenario: {}".format(scenario))


@pytest.mark.bench
@pytest.mark.parametrize("scenario", ["field_compute", "loader_call_sample", "row_write", "hub_emit_lazy"])
@pytest.mark.benchmark(group="observability-fastpath")
def test_bench_observability_fastpath_empty_overhead(benchmark, scenario: str) -> None:
    iters = _bench_iters()
    runner = BenchmarkRunner(benchmark)
    runner.run(_make_runner(scenario, iters), extra_info=_bench_info(scenario, iters))
