import logging

from scalim.ob.perf_metrics import PerformanceMetrics
from scalim.ob.presets.performance_presentation import PerformancePresentationLayer


def _make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers[:] = [logging.NullHandler()]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def test_percentile_edges() -> None:
    layer = PerformancePresentationLayer()
    assert layer._percentile([], 0.5) == 0.0
    assert layer._percentile([1.0, 2.0], 0.0) == 1.0
    assert layer._percentile([1.0, 2.0], 1.0) == 2.0


def test_console_lines_and_structured_early_returns_cover_empty_metrics() -> None:
    layer = PerformancePresentationLayer()
    metrics = PerformanceMetrics()
    logger = _make_logger("scalim.tests.performance_presentation.empty")

    assert layer._compute_loader_breakdown(metrics) is None
    assert layer._build_console_loader_breakdown_line(metrics) is None

    layer._emit_structured_loader_breakdown(metrics, logger=logger)
    layer._emit_structured_batch_stats(metrics, logger=logger)
    layer._emit_structured_loader_lines(metrics, logger=logger)

    lines = layer.iter_console_lines(
        metrics,
        include_loader_stats=True,
        include_loader_top_n=1,
        include_field_compute_top_n=1,
        include_advisor_hints=True,
    )
    assert lines and "summary" in lines[0]


def test_compute_batch_stats_defensive_empty_durations_branch() -> None:
    layer = PerformancePresentationLayer()
    metrics = PerformanceMetrics()

    class _TruthyButEmpty:
        def __len__(self):  # type: ignore[no-untyped-def]
            return 1

        def __iter__(self):  # type: ignore[no-untyped-def]
            return iter(())

    metrics.__dict__["batch_durations"] = _TruthyButEmpty()
    assert layer._compute_batch_stats(metrics) is None


def test_structured_console_report_covers_loader_field_top_and_hints() -> None:
    layer = PerformancePresentationLayer()
    metrics = PerformanceMetrics()
    logger = _make_logger("scalim.tests.performance_presentation.structured")

    metrics.total_duration = 10.0
    metrics.total_rows = 100
    metrics.batch_count = 2
    metrics.batch_durations = [1.0, 2.0]

    # stream dominates -> advisor hint
    metrics.stage_metrics.stream_duration = 6.0
    metrics.stage_metrics.loader_duration = 1.0
    metrics.stage_metrics.compute_duration = 1.0
    metrics.stage_metrics.write_duration = 1.0

    loader = metrics.get_loader_stats("orders")
    loader.record_call(0.2, 10, cache_status="miss")
    loader.record_call(0.1, 10, cache_status="hit")

    field = metrics.get_field_compute_stats("a")
    field.record_call(0.1)

    layer._emit_structured_console_report(
        metrics=metrics,
        include_loader_stats=True,
        include_loader_top_n=1,
        include_field_compute_top_n=1,
        include_advisor_hints=True,
        logger=logger,
    )

    layer._emit_structured_console_report(
        metrics=metrics,
        include_loader_stats=True,
        include_loader_top_n=1,
        include_field_compute_top_n=1,
        include_advisor_hints=False,
        logger=logger,
    )


def test_advisor_hints_cover_dominance_and_low_cache_paths() -> None:
    layer = PerformancePresentationLayer()

    metrics = PerformanceMetrics()
    metrics.stage_metrics.stream_duration = 10.0
    hints = list(layer._iter_advisor_hints(metrics))
    assert hints and "streaming-dominated" in hints[0][0]

    metrics = PerformanceMetrics()
    metrics.stage_metrics.loader_duration = 10.0
    hints = list(layer._iter_advisor_hints(metrics))
    assert hints and "lookup-dominated" in hints[0][0]

    metrics = PerformanceMetrics()
    metrics.stage_metrics.compute_duration = 10.0
    hints = list(layer._iter_advisor_hints(metrics))
    assert hints and "compute-bound" in hints[0][0]

    metrics = PerformanceMetrics()
    metrics.stage_metrics.write_duration = 10.0
    hints = list(layer._iter_advisor_hints(metrics))
    assert hints and "write-bound" in hints[0][0]

    metrics = PerformanceMetrics()
    metrics.stage_metrics.stream_duration = 1.0
    metrics.stage_metrics.loader_duration = 1.0
    metrics.stage_metrics.compute_duration = 1.0
    metrics.stage_metrics.write_duration = 1.0
    low_hit = metrics.get_loader_stats("customers")
    for _ in range(10):
        low_hit.record_call(0.01, 1, cache_status="miss")

    hints = list(layer._iter_advisor_hints(metrics))
    assert any("low cache hit-rate" in hint for hint, _severity in hints)
