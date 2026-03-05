import json

from scalim.ob.perf_metrics import (
    AdaptiveSchedulerMetrics,
    CpuSample,
    LoaderStats,
    MemorySample,
    PerformanceMetrics,
    StageMetrics,
)
from scalim.events.events import AdaptiveSchedulerDecisionEvent


def test_memory_sample_to_dict() -> None:
    sample = MemorySample(timestamp=1000.123456, rss_mb=512.789, label="test")
    d = sample.to_dict()
    assert d["timestamp"] == 1000.123
    assert d["rss_mb"] == 512.79
    assert d["label"] == "test"


def test_cpu_sample_to_dict() -> None:
    sample = CpuSample(timestamp=1000.5, percent=45.678, label="batch_1")
    d = sample.to_dict()
    assert d["timestamp"] == 1000.5
    assert d["percent"] == 45.68
    assert d["label"] == "batch_1"


def test_loader_stats_record_call() -> None:
    stats = LoaderStats(name="test_loader")
    assert stats.call_count == 0
    assert stats.exec_count == 0
    assert stats.avg_duration == 0.0

    stats.record_call(duration=0.5, record_count=100, cache_status="miss")
    stats.record_call(duration=1.5, record_count=200, cache_status="hit")

    assert stats.call_count == 2
    assert stats.exec_count == 1
    assert stats.cache_miss_count == 1
    assert stats.cache_hit_count == 1
    assert stats.total_duration == 2.0
    assert stats.total_records == 300
    assert stats.avg_duration == 1.0
    assert stats.min_duration == 0.5
    assert stats.max_duration == 1.5


def test_loader_stats_empty_min_max() -> None:
    stats = LoaderStats(name="empty")
    assert stats.min_duration == 0.0
    assert stats.max_duration == 0.0


def test_loader_stats_to_dict() -> None:
    stats = LoaderStats(name="loader1")
    stats.record_call(0.1, 10, cache_status="miss")
    d = stats.to_dict()
    assert d["name"] == "loader1"
    assert d["call_count"] == 1
    assert d["exec_count"] == 1
    assert d["cache_miss_count"] == 1
    assert d["cache_hit_count"] == 0
    assert d["cache_hit_rate"] == 0.0
    assert d["total_records"] == 10


def test_stage_metrics_to_dict() -> None:
    stages = StageMetrics(loader_duration=1.5, compute_duration=0.5, write_duration=0.3)
    d = stages.to_dict()
    assert d["loader"] == 1.5
    assert d["compute"] == 0.5
    assert d["write"] == 0.3


def test_performance_metrics_basic() -> None:
    metrics = PerformanceMetrics()
    assert metrics.throughput == 0.0
    assert metrics.avg_batch_duration == 0.0

    metrics.total_duration = 10.0
    metrics.total_rows = 1000
    metrics.batch_durations = [1.0, 2.0, 3.0]
    metrics.batch_count = 3

    assert metrics.throughput == 100.0
    assert metrics.avg_batch_duration == 2.0
    assert metrics.min_batch_duration == 1.0
    assert metrics.max_batch_duration == 3.0


def test_performance_metrics_memory_increase() -> None:
    metrics = PerformanceMetrics()
    assert metrics.memory_increase_mb is None

    metrics.start_memory_mb = 100.0
    metrics.end_memory_mb = 150.0
    assert metrics.memory_increase_mb == 50.0


def test_performance_metrics_get_loader_stats() -> None:
    metrics = PerformanceMetrics()
    stats1 = metrics.get_loader_stats("loader1")
    stats2 = metrics.get_loader_stats("loader1")
    assert stats1 is stats2

    stats1.record_call(0.1, 10, cache_status=None)
    assert metrics.loader_stats["loader1"].call_count == 1


def test_loader_stats_cache_hit_rate_zero_denominator() -> None:
    stats = LoaderStats(name="empty")
    assert stats.cache_hit_rate == 0.0
    stats.record_call(0.1, 1, cache_status=None)
    assert stats.cache_hit_rate == 0.0


def test_performance_metrics_to_dict() -> None:
    metrics = PerformanceMetrics()
    metrics.total_duration = 5.0
    metrics.batch_count = 2
    metrics.total_rows = 100
    metrics.batch_durations = [2.0, 3.0]

    d = metrics.to_dict()
    assert "summary" in d
    assert d["summary"]["total_duration"] == 5.0
    assert d["summary"]["throughput"] == 20.0
    assert "batches" in d
    assert "stages" in d
    assert "loaders" in d


def test_performance_metrics_to_dict_with_memory() -> None:
    metrics = PerformanceMetrics()
    metrics.memory_samples = [
        MemorySample(timestamp=1.0, rss_mb=100.0, label="start"),
        MemorySample(timestamp=2.0, rss_mb=150.0, label="end"),
    ]
    metrics.start_memory_mb = 100.0
    metrics.end_memory_mb = 150.0
    metrics.peak_memory_mb = 160.0

    d = metrics.to_dict()
    assert "memory" in d
    assert d["memory"]["start_mb"] == 100.0
    assert d["memory"]["peak_mb"] == 160.0
    assert len(d["memory"]["samples"]) == 2


def test_performance_metrics_to_dict_with_cpu() -> None:
    metrics = PerformanceMetrics()
    metrics.cpu_samples = [CpuSample(timestamp=1.0, percent=1.5, label="cpu")]

    d = metrics.to_dict()
    assert "cpu" in d
    assert d["cpu"]["samples"][0]["percent"] == 1.5


def test_performance_metrics_to_dict_with_adaptive_scheduler() -> None:
    metrics = PerformanceMetrics()
    metrics.adaptive_scheduler = AdaptiveSchedulerMetrics()

    d = metrics.to_dict()
    assert "adaptive_scheduler" in d


def test_performance_metrics_to_json() -> None:
    metrics = PerformanceMetrics()
    metrics.total_duration = 1.0
    metrics.batch_count = 1

    json_str = metrics.to_json()
    parsed = json.loads(json_str)
    assert "summary" in parsed


def test_performance_metrics_to_csv_rows() -> None:
    metrics = PerformanceMetrics()
    metrics.batch_durations = [1.0, 2.0, 3.0]

    rows = metrics.to_csv_rows()
    assert len(rows) == 3
    assert rows[0]["batch_num"] == 1
    assert rows[0]["duration"] == 1.0
    assert rows[2]["batch_num"] == 3


def test_performance_metrics_to_csv_rows_with_samples() -> None:
    metrics = PerformanceMetrics()
    metrics.batch_durations = [1.0, 2.0]
    metrics.memory_samples = [
        MemorySample(timestamp=1.0, rss_mb=100.0, label="b1"),
        MemorySample(timestamp=2.0, rss_mb=120.0, label="b2"),
    ]
    metrics.cpu_samples = [
        CpuSample(timestamp=1.0, percent=50.0, label="b1"),
        CpuSample(timestamp=2.0, percent=60.0, label="b2"),
    ]

    rows = metrics.to_csv_rows()
    assert len(rows) == 2
    assert rows[0]["memory_mb"] == 100.0
    assert rows[0]["cpu_percent"] == 50.0
    assert rows[1]["memory_mb"] == 120.0


def test_adaptive_scheduler_metrics_record_and_to_dict() -> None:
    metrics = AdaptiveSchedulerMetrics()

    metrics.record_decision(
        AdaptiveSchedulerDecisionEvent(
            batch_num=1,
            layer_index=0,
            decision="parallel",
            backend="thread",
            pool_limits={"db": 2},
            pool_wait_ms_total={"db": 12.5},
            pool_wait_ms_max={"db": 12.5},
            pool_wait_count={"db": 1},
        )
    )
    metrics.record_decision(
        AdaptiveSchedulerDecisionEvent(
            batch_num=1,
            layer_index=1,
            decision="serial",
            backend="thread",
            reason="below_min_parallel_tasks",
        )
    )
    metrics.record_decision(
        AdaptiveSchedulerDecisionEvent(
            batch_num=1,
            layer_index=2,
            decision="serial",
            backend="",
            reason="no_backend",
        )
    )

    d = metrics.to_dict()
    assert d["parallel_layers"] == 1
    assert d["serial_layers"] == 2
    assert d["serial_reasons"]["below_min_parallel_tasks"] == 1
    assert d["backends"]["thread"] == 2
    assert d["pools"]["limits"]["db"] == 2
    assert d["pools"]["wait_count"]["db"] == 1
