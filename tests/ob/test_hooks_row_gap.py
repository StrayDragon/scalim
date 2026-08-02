import logging

from scalim.events._events import LoaderCallEvent, PipelineEndEvent
from scalim.ob.presets.row_gap import ROW_GAP_LOG_PRIMARY, ROW_GAP_LOG_SUMMARY, RowGapObserver
from tests.support.event_envelope import event_envelope


def test_row_gap_primary_loader_records_count(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"})

    event = event_envelope(
        LoaderCallEvent(
            loader_name="primary",
            params={},
            result={1: {"id": 1}, 2: {"id": 2}},
            duration=0.1,
        )
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(event)

    assert hook._primary_count == 2
    assert any((ROW_GAP_LOG_PRIMARY % (2, "primary")) == record.getMessage() for record in caplog.records)


def test_row_gap_data_loader_tracks_missing_and_summary(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"}, sample_limit=2)

    data_event = event_envelope(
        LoaderCallEvent(
            loader_name="data",
            params={"batch_row_nth": [1, 2, 3]},
            result={1: {"id": 1}},
            duration=0.2,
        )
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(data_event)
        hook.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=1, total_duration=0.5)))

    assert hook.total_expected == 3
    assert hook.total_actual == 1
    assert hook.total_missing == 2
    assert any((ROW_GAP_LOG_SUMMARY % (3, 1, 2, None)) == record.getMessage() for record in caplog.records)


def test_row_gap_data_loader_handles_missing_expected_keys_and_skips_summary(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"}, sample_limit=1)

    data_event = event_envelope(
        LoaderCallEvent(
            loader_name="data",
            params={},
            result={1: {"id": 1}},
            duration=0.0,
        )
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(data_event)
        hook.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=0, total_duration=0.0)))

    assert hook.total_expected == 0
    assert not any(ROW_GAP_LOG_SUMMARY in record.getMessage() for record in caplog.records)


def test_row_gap_extract_expected_keys_and_result_size() -> None:
    assert RowGapObserver._extract_expected_keys({"batch_row_nth": [1, 2]}) == [1, 2]
    assert RowGapObserver._extract_expected_keys({"batch_keys": [1, 2]}) == [1, 2]
    assert RowGapObserver._extract_expected_keys({"keys": {"a": 1}}) == ["a"]
    assert RowGapObserver._extract_expected_keys({"user_ids": None}) is None
    assert RowGapObserver._extract_expected_keys({"ids": "bad"}) is None
    assert RowGapObserver._extract_expected_keys({"other": [1, 2]}) is None
    assert RowGapObserver._extract_expected_keys({}) is None

    assert RowGapObserver._result_size([1, 2, 3]) == 3
    assert RowGapObserver._result_size(object()) == 0


def test_row_gap_ignores_untracked_loader_and_unhashable_keys(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"}, sample_limit=1)

    untracked_event = event_envelope(
        LoaderCallEvent(
            loader_name="other",
            params={"batch_row_nth": [1]},
            result={},
            duration=0.1,
        )
    )

    bad_key_event = event_envelope(
        LoaderCallEvent(
            loader_name="data",
            params={"batch_row_nth": [[1]]},
            result={},
            duration=0.1,
        )
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(untracked_event)
        hook.on_loader_call(bad_key_event)

    assert hook.total_expected == 1
