import logging

from scalim.events._events import BatchEndEvent, BatchStartEvent, FieldSlimEvent, LoaderCallEvent, RowWriteEvent
from scalim.ob.presets.execution_trace import ExecutionTraceObserver, FieldSlimStep, LoaderCallStep, RowWriteStep
from tests.support.event_envelope import event_envelope


def test_tracer_steps_to_dict() -> None:
    loader_step = LoaderCallStep(loader_name="demo", params={"ids": {1, 2}}, result_count=2, duration=0.1)
    loader_dict = loader_step.to_dict()
    assert loader_dict["loader_name"] == "demo"

    field_step = FieldSlimStep(field_key="field", reason="test", remaining_fields=0)
    field_dict = field_step.to_dict()
    assert field_dict["field_key"] == "field"

    row_step = RowWriteStep(row_id=1, batch_num=2)
    row_dict = row_step.to_dict()
    assert row_dict["row_id"] == "1"

    row_step_none = RowWriteStep(row_id=None, batch_num=2)
    row_dict_none = row_step_none.to_dict()
    assert row_dict_none["row_id"] is None


def test_tracer_handlers_noop_when_batch_is_missing() -> None:
    observer = ExecutionTraceObserver()
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.2)))
    observer.on_field_slim(event_envelope(FieldSlimEvent(field_key="f", reason="test", batch_num=None, remaining_fields=0)))
    observer.on_row_write(event_envelope(RowWriteEvent(row_id=1, field_count=1, batch_num=None, row_index=0)))

    assert observer.batches == []
    assert observer.total_field_slims == 0
    assert observer.total_row_writes == 0


def test_tracer_serialize_params_handles_collections() -> None:
    params = {"ids": {1, 2}, "names": ["a", "b"], "pair": (1, 2), "plain": 3}
    serialized = LoaderCallStep.serialize_params(params)

    assert isinstance(serialized["ids"], str)
    assert "1" in serialized["ids"]
    assert serialized["names"] == str(["a", "b"])
    assert serialized["pair"] == str([1, 2])
    assert serialized["plain"] == "3"


def test_tracer_loader_call_records_step(caplog) -> None:
    observer = ExecutionTraceObserver()
    observer.on_batch_start(event_envelope(BatchStartEvent(batch_num=1, row_ids=[1, 2])))
    observer.on_loader_call(event_envelope(LoaderCallEvent(loader_name="demo", params={"ids": {1}}, result=[{"id": 1}], duration=0.1)))
    observer.on_batch_end(event_envelope(BatchEndEvent(batch_num=1, duration=0.2)))

    assert observer.total_loader_calls == 1
    assert len(observer.batches) == 1
    assert isinstance(observer.batches[0].steps[0], LoaderCallStep)

    logger = logging.getLogger("scalim.ob.presets.execution_trace")
    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.print_summary()

    assert caplog.records


def test_tracer_print_summary_empty(caplog) -> None:
    observer = ExecutionTraceObserver()
    logger = logging.getLogger("scalim.ob.presets.execution_trace")
    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.print_summary()
    assert caplog.records
