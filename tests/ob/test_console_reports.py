import logging

import pytest

from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    LoaderCallEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    StageSpanEvent,
)
from scalim.ob._internal.console_report import build_line, format_percent, format_seconds
from scalim.ob.metrics import MetricsCollector
from scalim.ob.perf_metrics import PerformanceMetrics, StageMetrics
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.performance_presentation import PerformancePresentationLayer
from scalim.ob.presets.relations import RelationConfig, RelationObserver


def test_console_report_build_line_orders_kv_and_omits_none() -> None:
    line = build_line("demo", "summary", {"b": 2, "a": 1, "skip": None})
    assert line.startswith("[scalim] demo:")
    assert "summary" in line
    assert "a=1, b=2" in line
    assert "skip" not in line


def test_console_report_helpers_handle_none() -> None:
    assert format_seconds(None) is None
    assert format_percent(None) is None


def test_console_report_build_line_requires_non_empty_kind() -> None:
    with pytest.raises(ValueError):
        _ = build_line("demo", "")

    with pytest.raises(ValueError):
        _ = build_line("demo", "   ")


def test_console_report_build_line_without_kv_has_no_suffix() -> None:
    line = build_line("demo", "summary")
    assert line == "[scalim] demo: summary"


def test_relations_console_report_is_line_oriented(caplog) -> None:
    logger = logging.getLogger("scalim.relations")
    observer = RelationObserver(config=RelationConfig(report_format="console", sampling_rate=1.0, logger=logger))

    observer.record_lookup(row_id=1, fk_raw=1, fk_normalized=1, target_source="customers", result="hit")
    observer.record_lookup(row_id=2, fk_raw=2, fk_normalized=2, target_source="customers", result="miss")
    observer.record_lookup(row_id=3, fk_raw=None, fk_normalized=None, target_source="customers", result="null_key")
    observer.record_lookup(
        row_id=4,
        fk_raw="x",
        fk_normalized="x",
        target_source="orders",
        result="type_error",
        fk_type="str",
        expected_type="int",
        error_message="type mismatch",
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.print_summary()

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[scalim] relations:" in text
    assert "summary" in text
    assert "total_lookups=" in text
    assert "hit_rate=" in text
    assert "per_source" in text
    assert "source=customers" in text
    assert "source=orders" in text
    assert "┌" not in text


def test_performance_console_report_contains_summary_and_breakdown(caplog) -> None:
    logger = logging.getLogger("scalim.performance")
    observer = PerformanceObserver(
        config=PerformanceConfig(metrics={"duration"}, report_format="console", include_details=True, logger=logger)
    )

    observer.on_pipeline_start(PipelineStartEvent(targets=["x"], batch_size=3))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2, 3]))
    observer.on_stage_span(StageSpanEvent(batch_num=1, stage="loader", duration=0.1))
    observer.on_stage_span(StageSpanEvent(batch_num=1, stage="compute", duration=0.05))
    observer.on_stage_span(StageSpanEvent(batch_num=1, stage="write", duration=0.02))
    observer.on_loader_call(LoaderCallEvent(loader_name="demo_loader", params={}, result=[{"x": 1}], duration=0.02))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.3))

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.3))

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[scalim] performance:" in text
    assert "summary" in text
    assert "total_duration_s=" in text
    assert "batch_count=" in text
    assert "stage" in text
    assert "loader" in text
    assert "┌" not in text


def test_metrics_collector_print_summary_early_returns_when_no_loaders(caplog) -> None:
    collector = MetricsCollector()

    with caplog.at_level(logging.INFO, logger="scalim.ob.metrics"):
        collector.print_summary()

    messages = [r.getMessage() for r in caplog.records if r.name == "scalim.ob.metrics"]
    assert len(messages) == 1
    assert "[scalim] metrics:" in messages[0]
    assert "summary" in messages[0]


def test_performance_presentation_render_summary_skips_zero_duration_stage() -> None:
    layer = PerformancePresentationLayer()
    metrics = PerformanceMetrics(
        total_duration=1.0,
        batch_count=1,
        total_rows=10,
        batch_durations=[1.0],
        stage_metrics=StageMetrics(loader_duration=1.0, compute_duration=0.0, write_duration=0.5),
    )

    rendered = layer.render_summary(metrics, include_details=False)

    assert "[scalim] performance:" in rendered
    assert "summary" in rendered
    assert "stage=loader" in rendered
    assert "stage=write" in rendered
    assert "stage=compute" not in rendered


def test_performance_presentation_output_report_supports_csv(tmp_path) -> None:  # type: ignore[no-untyped-def]
    layer = PerformancePresentationLayer()
    metrics = PerformanceMetrics(
        total_duration=0.1,
        batch_count=1,
        total_rows=10,
        batch_durations=[0.1],
    )
    output_path = tmp_path / "perf.csv"
    logger = logging.getLogger("scalim.performance.presentation")

    layer.output_report(
        metrics=metrics,
        report_format="csv",
        output_path=str(output_path),
        include_details=False,
        logger=logger,
    )

    assert output_path.exists()

    layer.output_report(
        metrics=metrics,
        report_format="unknown",
        output_path=str(output_path),
        include_details=False,
        logger=logger,
    )
