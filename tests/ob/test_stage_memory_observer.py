import sys

import pytest

from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    StageSpanEvent,
)
from scalim.ob.presets.stage_memory import PSUTIL_NOT_INSTALLED_WARNING_PREFIX, StageMemoryConfig, StageMemoryObserver
from scalim.ob.report_formats import ConsoleJsonlReportFormat
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


class _OsErrorProcess:
    def memory_info(self):  # type: ignore[no-untyped-def]
        raise OSError("boom")


class _OsErrorPsutil:
    def __init__(self) -> None:
        self._process = _OsErrorProcess()

    def Process(self):  # type: ignore[no-untyped-def]  # noqa: N802
        return self._process


def test_stage_memory_observer_records_samples_and_deltas(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())

    observer = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.NONE))
    observer.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    observer.on_stage_span(StageSpanEvent(stage="compute", batch_num=1, duration=0.02))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.03))
    observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.03))
    observer.close()

    assert len(observer.samples) >= 2
    assert observer.samples[0].rss_mb is not None
    assert observer.samples[0].delta_mb is not None
    assert observer.samples[0].delta_mb > 0


def test_stage_memory_observer_disables_when_psutil_missing(monkeypatch) -> None:
    with missing_optional_dependency(monkeypatch, "psutil"):
        with pytest.warns(UserWarning, match=PSUTIL_NOT_INSTALLED_WARNING_PREFIX):
            observer = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.NONE))

    assert observer.event_types == set()

    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    observer.close()
    assert observer.samples == []


def test_stage_memory_observer_auto_selects_jsonl_or_console(monkeypatch) -> None:
    import scalim.ob.presets.stage_memory as stage_memory_module

    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())

    calls = {"structured": 0, "console": 0}

    def _fake_emit_structured(_logger, *, level, kind, message, fields, ctx=None, exc_info=None):  # type: ignore[no-untyped-def]
        _ = level
        _ = message
        _ = ctx
        _ = exc_info
        assert kind == "stage_memory.sample"
        assert isinstance(fields, dict)
        calls["structured"] += 1

    def _fake_emit_info(_logger, subsystem, kind, mapping=None, **kwargs):  # type: ignore[no-untyped-def]
        _ = kind
        _ = mapping
        assert subsystem == "stage_memory"
        assert "batch_num" in kwargs
        calls["console"] += 1

    monkeypatch.setattr(stage_memory_module, "emit_structured", _fake_emit_structured)
    monkeypatch.setattr(stage_memory_module, "emit_info", _fake_emit_info)

    monkeypatch.setattr(stage_memory_module, "is_jsonl_logging_installed", lambda: True)
    observer = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.AUTO))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    observer.close()

    monkeypatch.setattr(stage_memory_module, "is_jsonl_logging_installed", lambda: False)
    observer2 = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.AUTO))
    observer2.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer2.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    observer2.close()

    assert calls["structured"] == 1
    assert calls["console"] == 1


def test_stage_memory_observer_default_config_branch_and_close(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())
    observer = StageMemoryObserver()
    observer.close()


def test_stage_memory_observer_disabled_config_hits_early_returns(monkeypatch) -> None:
    observer = StageMemoryObserver(config=StageMemoryConfig(enabled=False, report_format=ConsoleJsonlReportFormat.NONE))
    assert observer._get_rss_mb() is None  # noqa: SLF001

    observer.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
    observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.0))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.0))
    observer.close()


def test_stage_memory_observer_sampling_interval_skips_branches(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())
    observer = StageMemoryObserver(
        config=StageMemoryConfig(
            sampling_interval=2,
            report_format=ConsoleJsonlReportFormat.NONE,
        )
    )

    assert observer._should_sample(1) is False  # noqa: SLF001
    assert observer._should_sample(2) is True  # noqa: SLF001

    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
    observer.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.01))
    observer.close()
    assert observer.samples == []


def test_stage_memory_observer_rss_error_branches_are_defensive(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _OsErrorPsutil())
    observer = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.NONE))
    assert observer._get_rss_mb() is None  # noqa: SLF001
    assert observer._should_use_jsonl() is False  # noqa: SLF001

    observer.config.report_format = ConsoleJsonlReportFormat.JSONL
    assert observer._should_use_jsonl() is True  # noqa: SLF001

    observer.config.report_format = ConsoleJsonlReportFormat.CONSOLE
    assert observer._should_use_jsonl() is False  # noqa: SLF001

    observer.close()


def test_stage_memory_observer_stage_span_without_batch_start_has_no_delta(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil())
    observer = StageMemoryObserver(config=StageMemoryConfig(report_format=ConsoleJsonlReportFormat.NONE))

    observer.on_stage_span(StageSpanEvent(stage="loader", batch_num=1, duration=0.01))
    assert observer.samples
    assert observer.samples[0].delta_mb is None
    observer.close()
