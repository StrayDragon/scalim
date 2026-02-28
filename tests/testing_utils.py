from concurrent.futures import Future
from contextlib import contextmanager
import sys

from scalim.vendor.compact import importlibx
from scalim.sinks.sink_base import IColumnSink, IRowSink, ISink
from scalim.typedefs import FieldValue, RowData


class InlineExecutor:
    def submit(self, fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        fut = Future()
        fut.set_result(fn(*args, **kwargs))
        return fut


class NoOpLoadRefExecutor:
    def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
        _ = operator
        _ = context
        _ = batch_row_nth
        _ = runtime


class RecordingLoadRefExecutor:
    def __init__(self, calls) -> None:  # type: ignore[no-untyped-def]
        self._calls = calls

    def execute(self, operator, context, batch_row_nth, runtime) -> None:  # type: ignore[no-untyped-def]
        field_key = getattr(operator, "field_key", None)
        self._calls.append(field_key if field_key is not None else str(operator))
        _ = context
        _ = batch_row_nth
        _ = runtime


@contextmanager
def missing_optional_dependency(monkeypatch, module_name: str):
    real_import_module = importlibx.IMPORT_MODULE

    def _fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == module_name:
            raise ImportError(f"no {module_name}")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlibx, "IMPORT_MODULE", _fake_import)
    sys.modules.pop(module_name, None)

    try:
        yield
    finally:
        monkeypatch.setattr(importlibx, "IMPORT_MODULE", real_import_module)
        sys.modules.pop(module_name, None)


class ListSink(ISink):
    """将结果收集到内存列表中（批量模式）。"""

    def __init__(self) -> None:
        self.rows = []  # type: ignore[var-annotated]
        self.closed = False

    def write_batch(self, rows):  # type: ignore[no-untyped-def]
        self.rows.extend(rows)

    def close(self) -> None:
        self.closed = True


class StreamingListSink(IRowSink):
    """将结果收集到内存列表中（流式逐行模式）。"""

    def __init__(self) -> None:
        self.rows = []  # type: ignore[var-annotated]
        self.closed = False

    def write_row(self, row):  # type: ignore[no-untyped-def]
        self.rows.append(row)

    def close(self) -> None:
        self.closed = True


class ColumnListSink(IColumnSink):
    """将结果收集为列式的内存表示。"""

    def __init__(self) -> None:
        self.row_ids = []  # type: ignore[var-annotated]
        self.columns = {}  # type: ignore[var-annotated]
        self.closed = False

    def set_row_ids(self, row_ids):  # type: ignore[no-untyped-def]
        self.row_ids = list(row_ids)

    def write_column(self, field_key, values):  # type: ignore[no-untyped-def]
        if field_key not in self.columns:
            self.columns[field_key] = {}
        self.columns[field_key].update(values)

    def write_columns(self, columns):  # type: ignore[no-untyped-def]
        for field_key, values in columns.items():
            self.write_column(field_key, values)

    def close(self) -> None:
        self.closed = True

    def to_rows(self) -> "List[RowData]":
        rows = []
        for row_id in self.row_ids:
            row = {}
            for field_key, values in self.columns.items():
                row[field_key] = values.get(row_id)
            rows.append(row)
        return rows


__all__ = [
    "ColumnListSink",
    "InlineExecutor",
    "ListSink",
    "NoOpLoadRefExecutor",
    "RecordingLoadRefExecutor",
    "StreamingListSink",
    "missing_optional_dependency",
]
