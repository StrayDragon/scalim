import sys
import warnings

import pytest

from scalim.events._events import BatchEndEvent, PipelineEndEvent, PipelineStartEvent, StageSpanEvent
from scalim.ob.presets.performance import PSUTIL_NOT_INSTALLED_WARNING_PREFIX, PerformanceConfig, PerformanceObserver
from tests.support.testing_utils import missing_optional_dependency


class _FakeMemInfo:
    def __init__(self, rss: int) -> None:
        self.rss = rss


class _FakeProcess:
    def __init__(self) -> None:
        self._rss = 100 * 1024 * 1024

    def memory_info(self) -> _FakeMemInfo:
        info = _FakeMemInfo(self._rss)
        self._rss += 10 * 1024 * 1024
        return info


class _FakePsutil:
    def __init__(self) -> None:
        self._process = _FakeProcess()

    def Process(self) -> _FakeProcess:  # noqa: N802
        return self._process


def test_performance_observer_samples_memory(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())

    observer = PerformanceObserver(config=PerformanceConfig(metrics={"memory"}, report_format="none"))
    observer.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.01))
    observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.02))

    samples = observer.metrics.memory_samples
    assert samples is not None
    assert len(samples) >= 2
    assert observer.metrics.peak_memory_mb is not None


def test_performance_observer_memory_import_error(monkeypatch) -> None:
    with missing_optional_dependency(monkeypatch, "psutil"):
        with pytest.warns(UserWarning, match=PSUTIL_NOT_INSTALLED_WARNING_PREFIX):
            observer = PerformanceObserver(config=PerformanceConfig(metrics={"memory"}, report_format="none"))
        assert observer.metrics.memory_samples is None


def test_performance_observer_cpu_import_error(monkeypatch) -> None:
    with missing_optional_dependency(monkeypatch, "psutil"):
        with pytest.warns(UserWarning, match=PSUTIL_NOT_INSTALLED_WARNING_PREFIX):
            observer = PerformanceObserver(config=PerformanceConfig(metrics={"cpu"}, report_format="none"))
        assert observer.metrics.cpu_samples is None


def test_performance_observer_import_error_with_flaky_metrics_skips_disabled_metrics_warning(monkeypatch) -> None:
    import scalim.ob.presets.performance as performance_module

    class _FlakyMetrics:
        def __init__(self) -> None:
            self._calls = 0

        def __contains__(self, item) -> bool:  # type: ignore[no-untyped-def]
            self._calls += 1
            return bool(self._calls == 1 and item == "memory")

    def _raise_import_error(_name: str):  # type: ignore[no-untyped-def]
        raise ImportError("no psutil")

    monkeypatch.setattr(performance_module, "import_module", _raise_import_error)

    config = PerformanceConfig(metrics=_FlakyMetrics(), report_format="none")  # type: ignore[arg-type]
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        _ = PerformanceObserver(config=config)
    assert rec == []


def test_performance_observer_threshold_and_sampling_helpers_cover_missing_branches(monkeypatch, caplog) -> None:
    import scalim.ob.presets.performance as performance_module

    config = PerformanceConfig(
        metrics={"duration"},
        report_format="none",
    )
    config.thresholds.batch_duration_warn = 1.0
    config.thresholds.memory_increase_warn = 1.0

    class _NoResourceObserver(PerformanceObserver):
        def _get_memory_mb(self):  # type: ignore[no-untyped-def]
            return None

        def _get_cpu_percent(self):  # type: ignore[no-untyped-def]
            return None

    observer = _NoResourceObserver(config=config)

    observer.metrics.memory_samples = []
    observer.metrics.cpu_samples = []

    observer._sample_memory("x")  # noqa: SLF001
    observer._sample_cpu("x")  # noqa: SLF001

    with caplog.at_level("WARNING", logger=config.logger.name):
        observer._check_thresholds("batch_duration", 0.0)  # noqa: SLF001

        monkeypatch.setattr(performance_module, "format_kv", lambda *_a, **_kw: "")  # type: ignore[no-untyped-def]
        observer._check_thresholds("batch_duration", 2.0)  # noqa: SLF001
        observer._check_thresholds("memory_increase", 2.0)  # noqa: SLF001


def test_performance_observer_batch_end_skips_sampling_when_interval_not_reached() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none", sampling_interval=2))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.01))


def test_performance_observer_stage_span_ignores_unknown_stage() -> None:
    observer = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    observer.on_stage_span(StageSpanEvent(stage="unknown", batch_num=1, duration=0.01))
