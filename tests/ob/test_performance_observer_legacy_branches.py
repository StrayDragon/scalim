import logging

from scalim.events._events import BatchEndEvent, BatchStartEvent
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from tests.support.event_envelope import event_envelope


def test_performance_observer_batch_lines_legacy_omit_memory_cpu_when_unavailable(caplog) -> None:
    # ensure legacy branch (no JSONL handler installed)
    root = logging.getLogger("scalim")
    root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]

    logger = logging.getLogger("scalim.tests.performance.legacy")
    config = PerformanceConfig(metrics={"duration"}, report_format="console", include_batch_lines=True, logger=logger)
    obs = PerformanceObserver(config=config)

    obs.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1])))
    with caplog.at_level(logging.INFO, logger=logger.name):
        obs.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.1)))

    messages = [r.getMessage() for r in caplog.records]
    assert any("批次" in m for m in messages)
    assert all("memory=" not in m for m in messages)
    assert all("cpu=" not in m for m in messages)
