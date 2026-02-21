import logging

from scalim.events.events import LoaderCallEvent, PipelineEndEvent
from scalim.ob.presets.row_gap import RowGapObserver


def test_row_gap_primary_loader_records_count(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"})

    event = LoaderCallEvent(
        loader_name="primary",
        params={},
        result={1: {"id": 1}, 2: {"id": 2}},
        duration=0.1,
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(event)

    assert hook._primary_count == 2
    assert any("[RowGap] main_rows=2" in record.getMessage() for record in caplog.records)


def test_row_gap_data_loader_tracks_missing_and_summary(caplog) -> None:
    hook = RowGapObserver(primary_loader_name="primary", data_loader_names={"data"}, sample_limit=2)

    data_event = LoaderCallEvent(
        loader_name="data",
        params={"batch_row_nth": [1, 2, 3]},
        result={1: {"id": 1}},
        duration=0.2,
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(data_event)
        hook.on_pipeline_end(PipelineEndEvent(total_batches=1, total_duration=0.5))

    assert hook._total_expected == 3
    assert hook._total_actual == 1
    assert hook._total_missing == 2
    assert any("total expected=3" in record.getMessage() for record in caplog.records)


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

    untracked_event = LoaderCallEvent(
        loader_name="other",
        params={"batch_row_nth": [1]},
        result={},
        duration=0.1,
    )

    bad_key_event = LoaderCallEvent(
        loader_name="data",
        params={"batch_row_nth": [[1]]},
        result={},
        duration=0.1,
    )

    with caplog.at_level(logging.INFO, logger=hook.logger.name):
        hook.on_loader_call(untracked_event)
        hook.on_loader_call(bad_key_event)

    assert hook._total_expected == 1
