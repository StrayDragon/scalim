import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pytest

from scalim_benchlib import BenchmarkRunner
from notebooks.marimo.demo_big_data_report._loaders import ECommerceConfig, load_orders
from notebooks.marimo.demo_big_data_report._shared import (
    TARGET_FIELDS_BASIC,
    TARGET_FIELDS_DERIVED,
    TARGET_FIELDS_FULL,
    TARGET_FIELDS_RELATIONS,
    build_ecommerce_model,
)
from scalim._project_constants import ENV_BENCH_SCALE, ENV_BENCH_SCOPE
from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, run
from scalim.execution import ScalimEngine
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.row_gap import RowGapObserver
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink


def _bench_scale() -> str:
    return os.getenv(ENV_BENCH_SCALE, "small")


def _bench_scope() -> str:
    return os.getenv(ENV_BENCH_SCOPE, "notebook")


def _build_model() -> ECommerceConfig:
    cfg = ECommerceConfig.from_scale(_bench_scale())
    build_ecommerce_model(cfg)
    return cfg


def _bench_info(cfg: ECommerceConfig, scenario: str) -> Dict[str, object]:
    return {
        "scenario": scenario,
        "scale": _bench_scale(),
        "scope": _bench_scope(),
        "order_count": cfg.order_count,
        "customer_count": cfg.customer_count,
    }


def _make_pipeline_runner(
    cfg: ECommerceConfig,
    targets: List[str],
    batch_size: int,
    sink_factory: Callable[[], object],
    observer_factory: Optional[Callable[[], ObserverManager]] = None,
) -> Callable[[], int]:
    model = build_ecommerce_model(cfg)
    plan = PlanBuilder(model).build(targets=targets)

    def _run() -> int:
        observer_manager = observer_factory() if observer_factory else None
        engine = ScalimEngine(demand=model, plan=plan, observer_manager=observer_manager, batch_size=batch_size)
        with sink_factory() as sink:
            engine.run(main_rows=load_orders(), sink=sink)
        return cfg.order_count

    return _run


@pytest.mark.bench
@pytest.mark.benchmark(group="planning")
def test_bench_plan_build(benchmark) -> None:
    cfg = _build_model()
    model = build_ecommerce_model(cfg)

    def _build() -> None:
        PlanBuilder(model).build(targets=TARGET_FIELDS_FULL)

    runner = BenchmarkRunner(benchmark)
    runner.run(_build, extra_info=_bench_info(cfg, "plan_build"))


@pytest.mark.bench
@pytest.mark.benchmark(group="pipeline")
def test_bench_pipeline_full_column(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_FULL)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(cfg, TARGET_FIELDS_FULL, batch_size=100, sink_factory=_sink),
        extra_info=_bench_info(cfg, "pipeline_full_column"),
    )


@pytest.mark.bench
@pytest.mark.benchmark(group="pipeline")
def test_bench_pipeline_basic_row(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryRowSink:
        return InMemoryRowSink()

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(cfg, TARGET_FIELDS_BASIC, batch_size=100, sink_factory=_sink),
        extra_info=_bench_info(cfg, "pipeline_basic_row"),
    )


@pytest.mark.bench
@pytest.mark.benchmark(group="pipeline")
def test_bench_pipeline_relations(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_RELATIONS)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(cfg, TARGET_FIELDS_RELATIONS, batch_size=100, sink_factory=_sink),
        extra_info=_bench_info(cfg, "pipeline_relations"),
    )


@pytest.mark.bench
@pytest.mark.benchmark(group="pipeline")
def test_bench_pipeline_derived(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_DERIVED)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(cfg, TARGET_FIELDS_DERIVED, batch_size=100, sink_factory=_sink),
        extra_info=_bench_info(cfg, "pipeline_derived"),
    )


def _observer_manager_perf() -> ObserverManager:
    observer_manager = ObserverManager()
    perf_config = PerformanceConfig(metrics={"duration", "memory", "cpu"}, sampling_interval=1, report_format="none")
    observer_manager.register(PerformanceObserver(config=perf_config))
    return observer_manager


@pytest.mark.bench
@pytest.mark.benchmark(group="hooks")
def test_bench_pipeline_perf_hooks(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_FULL)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(
            cfg,
            TARGET_FIELDS_FULL,
            batch_size=100,
            sink_factory=_sink,
            observer_factory=_observer_manager_perf,
        ),
        extra_info=_bench_info(cfg, "pipeline_perf_hooks"),
    )


def _observer_manager_memory_opt() -> ObserverManager:
    observer_manager = ObserverManager()
    observer_manager.register(MemoryOptimizationObserver())
    return observer_manager


@pytest.mark.bench
@pytest.mark.benchmark(group="hooks")
def test_bench_pipeline_memory_opt(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_FULL)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(
            cfg,
            TARGET_FIELDS_FULL[:8],
            batch_size=50,
            sink_factory=_sink,
            observer_factory=_observer_manager_memory_opt,
        ),
        extra_info=_bench_info(cfg, "pipeline_memory_opt"),
    )


def _observer_manager_row_gap() -> ObserverManager:
    observer_manager = ObserverManager()
    observer_manager.register(
        RowGapObserver(
            primary_loader_name="primary_keys",
            data_loader_names={"base_info"},
            sample_limit=5,
        )
    )
    return observer_manager


@pytest.mark.bench
@pytest.mark.benchmark(group="hooks")
def test_bench_pipeline_row_gap(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_FULL[:8])

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(
            cfg,
            TARGET_FIELDS_FULL[:8],
            batch_size=100,
            sink_factory=_sink,
            observer_factory=_observer_manager_row_gap,
        ),
        extra_info=_bench_info(cfg, "pipeline_row_gap"),
    )


def _observer_manager_trace() -> ObserverManager:
    observer_manager = ObserverManager()
    observer_manager.register(ExecutionTraceObserver())
    return observer_manager


@pytest.mark.bench
@pytest.mark.benchmark(group="hooks")
def test_bench_pipeline_trace(benchmark) -> None:
    cfg = _build_model()

    def _sink() -> InMemoryColumnSink:
        return InMemoryColumnSink(field_names=TARGET_FIELDS_BASIC)

    runner = BenchmarkRunner(benchmark)
    runner.run(
        _make_pipeline_runner(
            cfg,
            TARGET_FIELDS_BASIC,
            batch_size=50,
            sink_factory=_sink,
            observer_factory=_observer_manager_trace,
        ),
        extra_info=_bench_info(cfg, "pipeline_trace"),
    )


@pytest.mark.bench
@pytest.mark.benchmark(group="dsl")
def test_bench_yaml_dsl(benchmark, tmp_path: Path) -> None:
    cfg = _build_model()
    yaml_path = Path("notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml")
    output_path = tmp_path / "ecommerce_report.csv"
    allowed_modules = frozenset(["notebooks.marimo.demo_big_data_report._loaders"])

    def _run_yaml() -> None:
        run(
            str(yaml_path),
            allowed_modules=allowed_modules,
            overrides=RunOverrides(output=OutputOverrides(path=str(output_path))),
            runtime_vars={"order_ids": []},
        )

    runner = BenchmarkRunner(benchmark)
    runner.run(_run_yaml, extra_info=_bench_info(cfg, "yaml_dsl"))


@pytest.mark.bench
@pytest.mark.benchmark(group="diagnostics")
def test_bench_relation_diagnostics(benchmark) -> None:
    cfg = _build_model()
    model = build_ecommerce_model(cfg)

    def _diagnose() -> int:
        count = 0
        for field in model.fields.values():
            if getattr(field, "relation", None) is not None:
                count += 1
        return count

    runner = BenchmarkRunner(benchmark)
    runner.run(_diagnose, extra_info=_bench_info(cfg, "relation_diagnostics"))
