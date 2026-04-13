import logging

from scalim.ob.metrics import LoaderMetrics, MetricsCollector


def test_loader_metrics_stats() -> None:
    metrics = LoaderMetrics(name="orders")

    assert metrics.avg_duration == 0.0
    assert metrics.min_duration == 0.0
    assert metrics.max_duration == 0.0

    metrics.record_call(0.5, 3)
    metrics.record_call(1.5, 5)

    assert metrics.call_count == 2
    assert metrics.total_records == 8
    assert metrics.avg_duration == 1.0
    assert metrics.min_duration == 0.5
    assert metrics.max_duration == 1.5


def test_metrics_collector_get_loader_metrics_returns_existing_instance() -> None:
    collector = MetricsCollector()
    m1 = collector.get_loader_metrics("orders")
    m2 = collector.get_loader_metrics("orders")
    assert m1 is m2


def test_metrics_collector_summary(caplog) -> None:
    collector = MetricsCollector()
    loader = collector.get_loader_metrics("orders")
    loader.record_call(0.2, 4)

    collector.record_batch(0.3, 4)

    with caplog.at_level(logging.INFO):
        collector.print_summary()

    summary = collector.get_summary_dict()
    assert summary["total_batches"] == 1
    assert summary["total_records"] == 4
    assert "orders" in summary["loaders"]
