from __future__ import annotations

from scalim.events.events import BatchEndEvent, BatchStartEvent, LoaderCallEvent, PipelineEndEvent, PipelineStartEvent
from scalim.ob.presets.logs import PrettyLoggingObserver


def test_pretty_logging_observer_renders_all_sections(capsys) -> None:
    observer = PrettyLoggingObserver()

    observer.on_pipeline_start(PipelineStartEvent(targets=["a", "b"], batch_size=3))
    observer.on_batch_start(BatchStartEvent(batch_num=1, row_ids=[1, 2, 3]))
    observer.on_batch_end(BatchEndEvent(batch_num=1, duration=0.12))

    observer.on_loader_call(
        LoaderCallEvent(
            loader_name="loader",
            params={},
            result=[1, 2],
            duration=0.01,
            batch_num=1,
            cache_status="hit",
            field_keys=["x"],
        )
    )
    observer.on_loader_call(
        LoaderCallEvent(
            loader_name="loader2",
            params={},
            result=None,
            duration=0.01,
            batch_num=1,
            cache_status="miss",
            field_keys=[],
        )
    )

    observer.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.2))

    captured = capsys.readouterr()
    assert "Scalim Pipeline" in captured.out
