from scalim.events import Event, EventType, PipelineStartEvent


def test_event_to_dict_keeps_non_dataclass_payload_as_is() -> None:
    event = Event(event_type=EventType.PIPELINE_START, timestamp=0.0, run_id="r", payload={"k": "v"}, meta={}, seq=1)
    out = event.to_dict()
    assert out["payload"] == {"k": "v"}
    assert type(out["event_type"]) is str
