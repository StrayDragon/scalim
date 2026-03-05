import io

import pytest

from scalim.sinks.sink_csv import CSVSink


class _FlushCounter:
    def __init__(self, raw, state) -> None:  # type: ignore[no-untyped-def]
        self._raw = raw
        self._state = state

    def write(self, data):  # type: ignore[no-untyped-def]
        return self._raw.write(data)

    def flush(self) -> None:
        self._state["count"] += 1
        self._raw.flush()

    def close(self) -> None:
        self._raw.close()

    def __getattr__(self, name):  # type: ignore[no-untyped-def]
        return getattr(self._raw, name)


def test_csv_sink_flush_policy_every_n_rows(tmp_path) -> None:
    state = {"count": 0}
    original_open = io.open

    def _open(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FlushCounter(original_open(*args, **kwargs), state)

    output_path = tmp_path / "rows.csv"
    sink = CSVSink(
        str(output_path),
        field_names=["id"],
        flush_policy="every_n_rows",
        flush_every_rows=2,
        open_fn=_open,
    )
    sink.write_row({"id": 1})
    sink.write_row({"id": 2})
    sink.write_row({"id": 3})
    sink.close()

    assert state["count"] == 1


def test_csv_sink_flush_policy_every_n_rows_batch(tmp_path) -> None:
    state = {"count": 0}
    original_open = io.open

    def _open(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FlushCounter(original_open(*args, **kwargs), state)

    output_path = tmp_path / "batch.csv"
    sink = CSVSink(
        str(output_path),
        field_names=["id"],
        flush_policy="every_n_rows",
        flush_every_rows=2,
        open_fn=_open,
    )
    sink.write_batch([{"id": 1}, {"id": 2}, {"id": 3}])
    sink.close()

    assert state["count"] == 1


def test_csv_sink_flush_policy_always_flushes_on_write_row(tmp_path) -> None:
    state = {"count": 0}
    original_open = io.open

    def _open(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _FlushCounter(original_open(*args, **kwargs), state)

    output_path = tmp_path / "always.csv"
    sink = CSVSink(
        str(output_path),
        field_names=["id"],
        flush_policy="always",
        open_fn=_open,
    )
    sink.write_row({"id": 1})
    sink.write_row({"id": 2})
    sink.close()

    assert state["count"] == 2


def test_csv_sink_flush_policy_invalid_value(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unknown flush_policy"):
        CSVSink(
            str(tmp_path / "invalid.csv"),
            field_names=["id"],
            flush_policy="never",
        )


def test_csv_sink_flush_policy_every_n_rows_requires_positive(tmp_path) -> None:
    with pytest.raises(ValueError, match="flush_every_rows must be >= 1"):
        CSVSink(
            str(tmp_path / "invalid.csv"),
            field_names=["id"],
            flush_policy="every_n_rows",
            flush_every_rows=0,
        )
