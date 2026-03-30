import logging

from scalim.events._events import BatchEndEvent, BatchStartEvent, LoaderCallEvent
from scalim.ob.presets.execution_trace import ExecutionTraceObserver, FieldSlimStep, LoaderCallStep, RowWriteStep


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
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2]))
    observer.on_loader_call(LoaderCallEvent(loader_name="demo", params={"ids": {1}}, result=[{"id": 1}], duration=0.1))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.2))

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
