import contextlib
import io
import logging

from scalim.events._events import BatchEndEvent, BatchStartEvent, OperatorSpanEvent
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.structured_logging import install_jsonl_logging


@contextlib.contextmanager
def _installed_jsonl(buf: io.StringIO):
    root = logging.getLogger("scalim")
    orig_handlers = list(root.handlers)
    orig_level = int(root.level)
    orig_propagate = bool(root.propagate)
    try:
        root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]
        install_jsonl_logging(stream=buf, profile="compact")
        yield
    finally:
        root.handlers[:] = orig_handlers
        root.setLevel(orig_level)
        root.propagate = orig_propagate


def test_performance_observer_batch_lines_use_structured_jsonl_when_installed() -> None:
    buf = io.StringIO()
    with _installed_jsonl(buf):
        logger = logging.getLogger("scalim.tests.performance.jsonl")
        obs = PerformanceObserver(
            config=PerformanceConfig(
                metrics={"duration"},
                report_format="console",
                include_batch_lines=True,
                logger=logger,
            )
        )
        obs.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2]))
        obs.on_batch_end(BatchEndEvent(batch_num=1, duration=0.1))

        # cover early-return branches in operator span handler
        obs.on_operator_span(OperatorSpanEvent(operator_type="load", field_key="a", batch_num=1, duration=0.1))
        obs.on_operator_span(OperatorSpanEvent(operator_type="compute", field_key=None, batch_num=1, duration=0.1))

    assert buf.getvalue()
