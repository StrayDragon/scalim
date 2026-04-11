import os
import threading
import traceback
from concurrent.futures import Future, TimeoutError
from contextlib import contextmanager
import sys
from typing import Any, Dict, List, cast

from scalim.planning.operators import LoadRefOperatorIr
from scalim.vendor.compact import importlibx
from scalim.sinks import IColumnSink, IRowSink, ISink
from scalim.typedefs import FieldValue, RowData

CI_TIMEOUT_S = float(os.environ.get("SCALIM_TEST_TIMEOUT", "10.0"))
NEGATIVE_TIMEOUT_S = float(os.environ.get("SCALIM_TEST_NEGATIVE_TIMEOUT", "2.0"))
POLL_DEADLINE_S = float(os.environ.get("SCALIM_TEST_POLL_DEADLINE", "5.0"))


def _format_thread_dump(*, label: str) -> str:
    frames = sys._current_frames()
    threads_by_id = {t.ident: t for t in threading.enumerate()}

    out: List[str] = []
    out.append("=== Thread dump: {} ===".format(str(label)))
    for thread_id, frame in frames.items():
        thread = threads_by_id.get(thread_id)
        if thread is None:
            out.append("Thread id={} <unknown>".format(thread_id))
        else:
            out.append(
                "Thread id={} name={!r} alive={} daemon={}".format(
                    thread_id,
                    str(thread.name),
                    bool(thread.is_alive()),
                    bool(thread.daemon),
                )
            )
        out.extend(line.rstrip("\n") for line in traceback.format_stack(frame))
        out.append("")
    return "\n".join(out)


def barrier_wait(barrier: threading.Barrier, *, timeout_s: float = CI_TIMEOUT_S, label: str) -> int:
    try:
        return barrier.wait(timeout=timeout_s)
    except threading.BrokenBarrierError as exc:
        msg = "Barrier wait failed: label={!r}, timeout_s={}\n{}".format(str(label), float(timeout_s), _format_thread_dump(label=label))
        raise RuntimeError(msg) from exc


def event_wait(event: threading.Event, *, timeout_s: float = CI_TIMEOUT_S, label: str) -> None:
    if event.wait(timeout=timeout_s):
        return
    msg = "Event wait timed out: label={!r}, timeout_s={}\n{}".format(str(label), float(timeout_s), _format_thread_dump(label=label))
    raise RuntimeError(msg)


def future_result(fut: Future, *, timeout_s: float = CI_TIMEOUT_S, label: str) -> Any:  # noqa: ANN401
    try:
        return fut.result(timeout=timeout_s)
    except TimeoutError as exc:
        msg = "Future result timed out: label={!r}, timeout_s={}\n{}".format(str(label), float(timeout_s), _format_thread_dump(label=label))
        raise RuntimeError(msg) from exc


def join_or_fail(thread: threading.Thread, *, timeout_s: float = CI_TIMEOUT_S, label: str) -> None:
    thread.join(timeout=timeout_s)
    if not thread.is_alive():
        return
    msg = "Thread join timed out: label={!r}, timeout_s={}\n{}".format(str(label), float(timeout_s), _format_thread_dump(label=label))
    raise RuntimeError(msg)


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
        load_ref_operator = cast("LoadRefOperatorIr", operator)  # pragma: allow-cast test executor typed narrowing
        self._calls.append(load_ref_operator.field_key)
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
    """Collect results into an in-memory list (batch mode)."""

    def __init__(self) -> None:
        self.rows = []  # type: ignore[var-annotated]
        self.closed = False

    def write_batch(self, rows):  # type: ignore[no-untyped-def]
        self.rows.extend(rows)

    def close(self) -> None:
        self.closed = True


class StreamingListSink(IRowSink):
    """Collect results into an in-memory list (streaming row mode)."""

    def __init__(self) -> None:
        self.rows = []  # type: ignore[var-annotated]
        self.closed = False

    def write_row(self, row):  # type: ignore[no-untyped-def]
        self.rows.append(row)

    def close(self) -> None:
        self.closed = True


class ColumnListSink(IColumnSink):
    """Collect results in a columnar in-memory representation."""

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
    "barrier_wait",
    "CI_TIMEOUT_S",
    "ColumnListSink",
    "InlineExecutor",
    "event_wait",
    "future_result",
    "join_or_fail",
    "ListSink",
    "NEGATIVE_TIMEOUT_S",
    "NoOpLoadRefExecutor",
    "POLL_DEADLINE_S",
    "RecordingLoadRefExecutor",
    "StreamingListSink",
    "missing_optional_dependency",
]
