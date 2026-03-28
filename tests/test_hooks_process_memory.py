import sys

import pytest

from scalim.events._events import BatchEndEvent, PipelineEndEvent, PipelineStartEvent
from scalim.ob.presets.performance import PSUTIL_NOT_INSTALLED_WARNING_PREFIX, PerformanceConfig, PerformanceObserver
from tests.testing_utils import missing_optional_dependency


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
