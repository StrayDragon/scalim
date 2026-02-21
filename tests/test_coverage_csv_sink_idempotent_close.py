from __future__ import annotations

from pathlib import Path

from scalim.sinks.sink_csv import CSVSink


def test_csv_sink_close_is_idempotent(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    sink = CSVSink(
        output_path=str(output_path),
        field_names=["id"],
        header_names=["ID"],
        include_header=True,
        flush_policy="always",
    )
    sink.write_row({"id": 1})
    sink.close()
    sink.close()
    assert output_path.exists()
