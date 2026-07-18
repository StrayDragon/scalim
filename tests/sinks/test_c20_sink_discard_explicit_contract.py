"""c20: ISink.discard is an explicit ABC contract (not duck-typed only)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pytest

from scalim.sinks import CSVSink, ExcelSink
from scalim.sinks._internal.base import BaseRowSink, ISink, discard_sink, exit_sink
from scalim.typedefs import RowData


def test_isink_requires_discard() -> None:
    class _MissingDiscard(ISink):
        def write_batch(self, rows: Sequence[RowData]) -> None:
            _ = rows

        def close(self) -> None:
            return None

    with pytest.raises(TypeError, match=r"discard"):
        _MissingDiscard()  # type: ignore[abstract]


def test_base_row_sink_default_discard_is_callable_noop() -> None:
    class _Collect(BaseRowSink):
        def __init__(self) -> None:
            self.rows: list[RowData] = []

        def write_row(self, row: RowData) -> None:
            self.rows.append(dict(row))

    sink = _Collect()
    sink.write_row({"a": 1})
    sink.discard()
    sink.discard()  # idempotent
    assert sink.rows == [{"a": 1}]


def test_discard_sink_calls_method_not_close() -> None:
    class _Track(BaseRowSink):
        def __init__(self) -> None:
            self.closed = False
            self.discarded = False

        def write_row(self, row: RowData) -> None:
            _ = row

        def close(self) -> None:
            self.closed = True

        def discard(self) -> None:
            self.discarded = True

    sink = _Track()
    discard_sink(sink)
    assert sink.discarded is True
    assert sink.closed is False


def test_exit_sink_failure_discards_success_closes() -> None:
    class _Track(BaseRowSink):
        def __init__(self) -> None:
            self.closed = False
            self.discarded = False

        def write_row(self, row: RowData) -> None:
            _ = row

        def close(self) -> None:
            self.closed = True

        def discard(self) -> None:
            self.discarded = True

    ok = _Track()
    exit_sink(ok, None)
    assert ok.closed is True
    assert ok.discarded is False

    bad = _Track()
    exit_sink(bad, RuntimeError)
    assert bad.discarded is True
    assert bad.closed is False


def test_csv_file_sink_discard_does_not_promote(tmp_path: Path) -> None:
    path = tmp_path / "out.csv"
    sink = CSVSink(str(path), field_names=["id"])
    sink.write_row({"id": 1})
    sink.discard()
    assert not path.exists()


def test_excel_file_sink_discard_does_not_promote(tmp_path: Path) -> None:
    path = tmp_path / "out.xlsx"
    sink = ExcelSink(str(path), field_names=["id"])
    sink.write_row({"id": 1})
    sink.discard()
    assert not path.exists()


def test_memory_and_pandas_discard_clears_and_is_idempotent(tmp_path: Path) -> None:
    from scalim.sinks import BlockColumnCSVSink, ExcelWorkbookSink
    from scalim.sinks._internal.memory import InMemoryColumnSink, InMemoryRowDataSink
    from scalim.sinks._internal.pandas import PandasColumnSink, PandasRowSink
    from scalim.sinks._internal.sink_csv import InMemoryCsvSink

    row = InMemoryRowDataSink()
    row.write_row({"a": 1})
    row.discard()
    assert row.get_data() == []
    row.discard()  # already closed early-return

    col = InMemoryColumnSink(["a"])
    col.set_row_ids([1])
    col.write_column("a", {1: 9})
    col.discard()
    assert col.get_columns() == {}
    col.discard()

    csv_mem = InMemoryCsvSink(field_names=["a"])
    csv_mem.write_row({"a": 1})
    csv_mem.discard()
    csv_mem.discard()

    prow = PandasRowSink()
    prow.write_row({"a": 1})
    prow.discard()
    assert prow.get_rows() == []
    prow.discard()

    pcol = PandasColumnSink(["a"])
    pcol.set_row_ids([1])
    pcol.write_column("a", {1: 2})
    pcol.discard()
    assert pcol.get_columns() == {}
    pcol.discard()

    block_path = tmp_path / "block.csv"
    block = BlockColumnCSVSink(str(block_path), ["a"], col_width=8, write_delay=0.0)
    block.discard()  # `_file is None` branch
    block2 = BlockColumnCSVSink(str(tmp_path / "block2.csv"), ["a"], col_width=8, write_delay=0.0)
    block2.set_row_ids([1])
    block2.write_column("a", {1: "x"})
    block2.discard()
    block2.discard()

    book = ExcelWorkbookSink(str(tmp_path / "wb.xlsx"))
    sheet = book.create_sheet_row_sink("s1", field_names=["id"])
    sheet.write_row({"id": 1})
    sheet.discard()
    sheet.discard()  # early return when already closed
    book.discard()


def test_router_discard_skips_non_callable_discard_attr() -> None:
    from scalim.execution.output_composition.router import FinalTargetState, RouteState, RouterRowSink
    from scalim.execution.output_composition.sinks import RowCounter

    class _NonCallableDiscard:
        discard = None

        def write_row(self, row: object) -> None:
            _ = row

        def close(self) -> None:
            return None

    router = RouterRowSink(
        routes=[
            RouteState(
                target_id="t",
                sink=_NonCallableDiscard(),  # type: ignore[arg-type]
                predicate=None,
                is_primary=True,
                output_path=None,
                sheet_name=None,
            )
        ],
        failure_policy="all_fail",
        workbook_resources=[],
        meta_target=FinalTargetState(
            target_id="meta",
            sink=_NonCallableDiscard(),  # type: ignore[arg-type]
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
        audit_target=FinalTargetState(
            target_id="audit",
            sink=_NonCallableDiscard(),  # type: ignore[arg-type]
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
    )
    router.discard()
