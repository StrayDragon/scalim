import os
from typing import Callable, Dict, List

import pytest

from scalim_benchlib import BenchmarkRunner
from scalim._project_constants import ENV_BENCH_MAX_WORKERS, ENV_BENCH_SCALE, ENV_BENCH_SCOPE
from scalim.execution import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DerivedFieldIr, FieldIr
from scalim.spec.ir import MainSourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr


def _bench_scale() -> str:
    return os.getenv(ENV_BENCH_SCALE, "small")


def _bench_scope() -> str:
    return os.getenv(ENV_BENCH_SCOPE, "parallel-throughput")


def _bench_row_count() -> int:
    scale = _bench_scale()
    return {
        "small": 200,
        "medium": 1000,
        "large": 5000,
    }.get(scale, 200)


def _bench_max_workers() -> int:
    raw = os.getenv(ENV_BENCH_MAX_WORKERS, "0")
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 0
    return parsed


def _bench_info(parallel_mode: str, row_count: int) -> Dict[str, object]:
    return {
        "scenario": "adaptive_execution",
        "scope": _bench_scope(),
        "scale": _bench_scale(),
        "row_count": row_count,
        "parallel_mode": parallel_mode,
    }


def _cpu_work(order_id: int) -> int:
    acc = int(order_id or 0)
    for _ in range(600):
        acc = (acc * 1103515245 + 12345) & 0x7FFFFFFF
    return acc


def _load_empty_orders() -> List[dict]:
    return []


def _build_demand() -> DemandIr:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    fields = [
        FieldIr(field_id="order_id", name="order_id", source=main_source, is_primary=True),
        DerivedFieldIr(
            field_id="work",
            name="work",
            dependencies=("order_id",),
            call_by=CallBySpecIr(
                reference=RuntimeHandleIdIr(handle_id="work.calculator"),
                kwargs=(("order_id", CallByValueIr(kind="field", value="order_id")),),
                field_names=("order_id",),
            ),
        ),
    ]
    return DemandIr.from_irs(sources=[], fields=fields, main_source=main_source)


def _make_rows(row_count: int) -> List[dict]:
    return [{"order_id": idx} for idx in range(row_count)]


def _make_runner(parallel_mode: str, row_count: int) -> Callable[[], int]:
    demand = _build_demand()
    plan = PlanBuilder(demand).build(targets=["work"])
    runtime_bindings = RuntimeBindings(
        derived_calculators={"work": _cpu_work},
    )
    rows = _make_rows(row_count)

    def _run() -> int:
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=runtime_bindings,
            parallel_mode=parallel_mode,  # type: ignore[arg-type]
            batch_size=50,
            max_workers=_bench_max_workers(),
        )
        results = engine.run(main_rows=rows)
        return len(results)

    return _run


_BenchCase = str


@pytest.mark.bench
@pytest.mark.benchmark(group="parallel-throughput")
@pytest.mark.parametrize(
    "case",
    [
        "seq",
        "adaptive",
    ],
    ids=[
        "seq",
        "adaptive",
    ],
)
def test_bench_parallel_pipeline_throughput(benchmark, case: _BenchCase) -> None:
    row_count = _bench_row_count()
    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_runner(case, row_count),
        extra_info=_bench_info(case, row_count),
    )
