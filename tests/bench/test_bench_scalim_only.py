import os
from typing import Callable, Dict, List

import pytest

from scalim_benchlib import BenchmarkRunner
from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryRowDataSink
from scalim.spec.ir import DemandIr
from scalim.spec.ir import DerivedFieldIr, FieldIr
from scalim.spec.ir import MainSourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr


def _bench_scale() -> str:
    return os.getenv("SCALIM_BENCH_SCALE", "small")


def _bench_scope() -> str:
    return os.getenv("SCALIM_BENCH_SCOPE", "scalim-only")


def _bench_row_count() -> int:
    scale = _bench_scale()
    return {
        "small": 200,
        "medium": 1000,
        "large": 5000,
    }.get(scale, 200)


def _bench_info(scenario: str, row_count: int) -> Dict[str, object]:
    return {
        "scenario": scenario,
        "scale": _bench_scale(),
        "scope": _bench_scope(),
        "row_count": row_count,
    }


def _build_demand() -> DemandIr:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    fields = [
        FieldIr(field_id="order_id", name="order_id", source=main_source, is_primary=True),
        FieldIr(field_id="amount", name="amount", source=main_source),
        FieldIr(field_id="cost", name="cost", source=main_source),
        DerivedFieldIr(
            field_id="profit",
            name="profit",
            dependencies=("amount", "cost"),
            compute_expr="amount - cost",
        ),
    ]
    return DemandIr.from_irs(sources=[], fields=fields, main_source=main_source)


def _make_rows(row_count: int) -> List[dict]:
    return [{"order_id": idx, "amount": idx * 1.0, "cost": idx * 0.4} for idx in range(row_count)]


def _make_pipeline_runner(row_count: int) -> Callable[[], int]:
    demand = _build_demand()
    plan = PlanBuilder(demand).build(targets=["order_id", "profit"])
    runtime_bindings = RuntimeBindings(
        derived_calculators={"profit": lambda amount, cost: (amount or 0) - (cost or 0)},
    )
    rows = _make_rows(row_count)

    def _run() -> int:
        engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=50)
        with InMemoryRowDataSink() as sink:
            engine.run(main_rows=rows, sink=sink)
        return row_count

    return _run


@pytest.mark.bench
@pytest.mark.benchmark(group="baseline")
def test_bench_scalim_only_plan_build(benchmark) -> None:
    demand = _build_demand()
    row_count = _bench_row_count()

    def _build() -> None:
        PlanBuilder(demand).build(targets=["order_id", "profit"])

    runner = BenchmarkRunner(benchmark)
    runner.run(_build, extra_info=_bench_info("plan_build", row_count))


@pytest.mark.bench
@pytest.mark.benchmark(group="baseline")
def test_bench_scalim_only_pipeline(benchmark) -> None:
    row_count = _bench_row_count()
    runner = BenchmarkRunner(benchmark)
    runner.run(_make_pipeline_runner(row_count), extra_info=_bench_info("pipeline_basic_row", row_count))
