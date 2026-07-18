from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from scalim.sinks._internal.rows import (
    InMemoryRows,
    InMemoryRowsSink,
    in_memory_rows_to_in_memory_csv,
    iter_in_memory_rows_as_main_rows,
)


def test_in_memory_rows_rejects_invalid_header_item() -> None:
    with pytest.raises(ValueError, match=r"InMemoryRows\.header\[0\]"):
        _ = InMemoryRows(header=[""], rows=[])


def test_in_memory_rows_rejects_row_length_mismatch() -> None:
    with pytest.raises(ValueError, match=r"length mismatch"):
        _ = InMemoryRows(header=["a", "b"], rows=[[1]])


def test_in_memory_rows_accepts_arbitrary_objects() -> None:
    sentinel = object()
    artifact = InMemoryRows(header=["a"], rows=[[sentinel]])
    assert artifact.rows[0][0] is sentinel


def test_in_memory_rows_iter_row_data_zips_header_and_values() -> None:
    artifact = InMemoryRows(header=["a", "b"], rows=[[1, None]])
    assert list(artifact.iter_row_data()) == [{"a": 1, "b": None}]


def test_in_memory_rows_sink_captures_typed_values() -> None:
    sink = InMemoryRowsSink(field_ids=["a", "b"])
    sink.write_row({"a": 1, "b": None})
    sink.write_batch([{"a": 2, "b": Decimal("1.5")}])
    sink.close()

    artifact = sink.to_artifact()
    assert artifact.header == ["a", "b"]
    assert artifact.rows == [[1, None], [2, Decimal("1.5")]]


def test_in_memory_rows_sink_requires_field_ids() -> None:
    with pytest.raises(ValueError, match=r"field_ids"):
        _ = InMemoryRowsSink(field_ids=None)  # type: ignore[arg-type]


def test_in_memory_rows_sink_preserves_temporal_field_values() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    d = date(2024, 1, 2)
    t = time(3, 4, 5)
    td = timedelta(days=1, seconds=30)
    aware = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    sink = InMemoryRowsSink(field_ids=["dt", "d", "t", "td", "aware"])
    sink.write_row(
        {  # pyright: ignore[reportArgumentType]
            "dt": dt,
            "d": d,
            "t": t,
            "td": td,
            "aware": aware,
        }
    )
    artifact = sink.to_artifact()
    assert artifact.rows == [[dt, d, t, td, aware]]
    assert artifact.rows[0][4].tzinfo is timezone.utc  # type: ignore[union-attr]


def test_in_memory_rows_sink_preserves_dict_and_custom_object() -> None:
    sink = InMemoryRowsSink(field_ids=["obj", "mapping"])
    sentinel = object()
    sink.write_row({"obj": sentinel, "mapping": {"bad": "x"}})
    artifact = sink.to_artifact()
    assert artifact.rows[0][0] is sentinel
    assert artifact.rows[0][1] == {"bad": "x"}


def test_in_memory_rows_accepts_temporal_on_construct() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    artifact = InMemoryRows(header=["dt", "d"], rows=[[dt, date(2024, 1, 2)]])
    assert artifact.rows[0][0] is dt


def test_in_memory_rows_to_in_memory_csv_stringifies_temporal() -> None:
    dt = datetime(2024, 1, 2, 3, 4, 5)
    artifact = InMemoryRows(header=["dt", "n"], rows=[[dt, None]])
    csv_artifact = in_memory_rows_to_in_memory_csv(artifact)
    assert csv_artifact.rows == [["2024-01-02 03:04:05", ""]]


def test_in_memory_rows_to_in_memory_csv_preserves_order_and_normalizes_values() -> None:
    artifact = InMemoryRows(header=["a", "b"], rows=[[None, Decimal("1.5")], [True, 2]])
    csv_artifact = in_memory_rows_to_in_memory_csv(artifact)
    assert csv_artifact.header == ["a", "b"]
    assert csv_artifact.rows == [["", "1.5"], ["True", "2"]]


def test_iter_in_memory_rows_as_main_rows_is_reiterable() -> None:
    artifact = InMemoryRows(header=["a"], rows=[[1], [2]])
    rows = iter_in_memory_rows_as_main_rows(artifact)
    assert list(rows) == [{"a": 1}, {"a": 2}]
    assert list(rows) == [{"a": 1}, {"a": 2}]


def test_in_memory_rows_sink_preserves_numpy_datetime64() -> None:
    np = pytest.importorskip("numpy")
    value = np.datetime64("2024-01-02T03:04:05")
    sink = InMemoryRowsSink(field_ids=["v"])
    sink.write_row({"v": value})
    assert sink.to_artifact().rows[0][0] is value
