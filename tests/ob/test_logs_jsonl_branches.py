import contextlib
import io
import logging

from scalim.ob.presets import logs as logs_preset
from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    ColumnWriteEvent,
    DiagnosticWarningEvent,
    ErrorEvent,
    FieldComputeEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    LoaderSlimEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from scalim.ob.presets.logs import LoggingObserver, PrettyLoggingObserver
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


def test_logging_observer_jsonl_branches() -> None:
    buf = io.StringIO()
    with _installed_jsonl(buf):
        logger = logging.getLogger("scalim.tests.logs")
        obs = LoggingObserver(logger=logger)

        obs.on_pipeline_start(PipelineStartEvent(targets=["a", "b"], batch_size=None))
        obs.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2]))
        obs.on_loader_call(
            LoaderCallEvent(
                loader_name="demo",
                params={"x": 1},
                result={1: {"x": 1}},
                duration=0.01,
                cache_status="hit",
                field_keys=["a"],
            )
        )
        obs.on_field_compute(FieldComputeEvent(field_key="a", row_id=1, dependencies={}, result=1))
        obs.on_field_slim(FieldSlimEvent(field_key="a", reason="demo", batch_num=1, remaining_fields=1))
        obs.on_row_write(RowWriteEvent(row_id=1, field_count=1, batch_num=1, row_index=0))
        obs.on_row_release(RowReleaseEvent(row_id=1, released_fields=["a"], retained_fields=["b"], batch_num=1))
        obs.on_loader_slim(LoaderSlimEvent(loader_name="demo", original_keys=3, extracted_fields=["a"], batch_num=1))
        obs.on_column_write(ColumnWriteEvent(field_key="a", row_count=1, batch_num=1))

        obs.on_diagnostic_warning(
            DiagnosticWarningEvent(
                message="warn",
                source_id="s",
                field_id="f",
                lookup_key="k",
                row_id=1,
            )
        )
        obs.on_error(ErrorEvent(error=ValueError("boom"), context={"x": 1}))

        obs.on_batch_end(BatchEndEvent(batch_num=1, duration=0.2))
        obs.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.2))

    assert buf.getvalue()


def test_pretty_logging_observer_jsonl_branches() -> None:
    buf = io.StringIO()
    with _installed_jsonl(buf):
        obs = PrettyLoggingObserver()
        obs.on_pipeline_start(PipelineStartEvent(targets=["a"], batch_size=1))
        obs.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1]))
        obs.on_loader_call(
            LoaderCallEvent(
                loader_name="demo",
                params={},
                result=[1, 2, 3],
                duration=0.01,
                cache_status="miss",
            )
        )
        obs.on_batch_end(BatchEndEvent(batch_num=1, duration=0.02))
        obs.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.02))

    assert buf.getvalue()


def test_pretty_logging_observer_removes_owned_stdout_handler_when_switching_to_jsonl() -> None:
    root = logging.getLogger("scalim")
    orig_root_handlers = list(root.handlers)
    orig_root_level = int(root.level)
    orig_root_propagate = bool(root.propagate)

    pretty_logger = logs_preset._PRETTY_LOGGER
    orig_pretty_handlers = list(pretty_logger.handlers)
    orig_pretty_level = int(pretty_logger.level)
    orig_pretty_propagate = bool(pretty_logger.propagate)

    slot = logs_preset._pretty_stdout_handler_slot
    orig_slot_handler = slot.handler
    orig_slot_owned = slot.owned

    try:
        root.handlers[:] = [h for h in root.handlers if getattr(h, "name", "") != "scalim.jsonl"]

        pretty_logger.handlers[:] = [h for h in pretty_logger.handlers if h.name != logs_preset._PRETTY_STDOUT_HANDLER_NAME]
        slot.handler = None
        slot.owned = False

        PrettyLoggingObserver()
        owned_handler = slot.handler
        assert slot.owned is True
        assert owned_handler is not None
        assert owned_handler in pretty_logger.handlers

        buf = io.StringIO()
        install_jsonl_logging(stream=buf, profile="compact")
        PrettyLoggingObserver._ensure_pretty_logger_ready()

        assert owned_handler not in pretty_logger.handlers
        assert slot.handler is None
        assert slot.owned is False
    finally:
        root.handlers[:] = orig_root_handlers
        root.setLevel(orig_root_level)
        root.propagate = orig_root_propagate

        pretty_logger.handlers[:] = orig_pretty_handlers
        pretty_logger.setLevel(orig_pretty_level)
        pretty_logger.propagate = orig_pretty_propagate

        slot.handler = orig_slot_handler
        slot.owned = orig_slot_owned
