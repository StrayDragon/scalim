import logging
import threading
import time
from pathlib import Path
from typing import List, Type

import pytest

from scalim.sinks import CSVSink, ColumnCSVSink
from scalim.sinks._internal import sink_csv as sink_csv_mod

_TIMEOUT_S = 5.0


def _create_sink(sink_cls: Type[object], output_path: Path, *, value: int, write_lock: bool) -> object:
    sink: object = sink_cls(str(output_path), field_names=["id"], write_lock=write_lock)
    if sink_cls is CSVSink:
        sink.write_row({"id": value})  # type: ignore[attr-defined]
    else:
        sink.set_row_ids([value])  # type: ignore[attr-defined]
        sink.write_column("id", {value: value})  # type: ignore[attr-defined]
    return sink


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_write_lock_removes_lock_file(tmp_path: Path, sink_cls) -> None:
    output_path = tmp_path / "locked.csv"
    lock_path = Path(str(output_path) + ".scalim.lock")

    sink = _create_sink(sink_cls, output_path, value=1, write_lock=True)
    sink.close()  # type: ignore[attr-defined]

    assert output_path.exists()
    assert lock_path.exists() is False


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_write_lock_conflict_fails_fast(tmp_path: Path, sink_cls) -> None:
    output_path = tmp_path / "locked_conflict.csv"
    lock_path = Path(str(output_path) + ".scalim.lock")
    lock_path.write_text("held", encoding="utf-8")

    sink = _create_sink(sink_cls, output_path, value=1, write_lock=True)
    with pytest.raises(RuntimeError, match="Output path is locked"):
        sink.close()  # type: ignore[attr-defined]

    assert output_path.exists() is False
    assert lock_path.exists() is True


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_write_lock_concurrent_writers_fail_fast(tmp_path: Path, sink_cls, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "concurrent.csv"
    lock_path = Path(str(output_path) + ".scalim.lock")

    sink1 = _create_sink(sink_cls, output_path, value=1, write_lock=True)
    sink2 = _create_sink(sink_cls, output_path, value=2, write_lock=True)

    blocked_in_replace = threading.Event()
    continue_replace = threading.Event()
    original_replace = Path.replace

    def _replace(self: Path, target: object) -> Path:  # noqa: ANN001
        if str(target) == str(output_path) and not blocked_in_replace.is_set():
            blocked_in_replace.set()
            if not continue_replace.wait(timeout=_TIMEOUT_S):
                raise RuntimeError("test timeout waiting to continue replace")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _replace)

    barrier = threading.Barrier(2)
    errors: List[BaseException] = []

    def _run(sink: object) -> None:
        try:
            _ = barrier.wait(timeout=_TIMEOUT_S)
            sink.close()  # type: ignore[attr-defined]
        except BaseException as exc:
            errors.append(exc)

    t1 = threading.Thread(target=lambda: _run(sink1), daemon=True)
    t2 = threading.Thread(target=lambda: _run(sink2), daemon=True)
    t1.start()
    t2.start()

    assert blocked_in_replace.wait(timeout=_TIMEOUT_S)
    deadline = time.time() + _TIMEOUT_S
    while time.time() < deadline and errors == []:
        time.sleep(0.01)
    continue_replace.set()

    t1.join(timeout=_TIMEOUT_S)
    t2.join(timeout=_TIMEOUT_S)
    assert not t1.is_alive()
    assert not t2.is_alive()

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert "Output path is locked" in str(errors[0])

    assert output_path.exists() is True
    assert lock_path.exists() is False


@pytest.mark.parametrize(
    "sink_cls",
    [CSVSink, ColumnCSVSink],
    ids=["row-sink", "column-sink"],
)
def test_csv_sink_without_write_lock_ignores_existing_lock_file(tmp_path: Path, sink_cls) -> None:
    output_path = tmp_path / "ignore_lock.csv"
    lock_path = Path(str(output_path) + ".scalim.lock")
    lock_path.write_text("held", encoding="utf-8")

    sink = _create_sink(sink_cls, output_path, value=1, write_lock=False)
    sink.close()  # type: ignore[attr-defined]

    assert output_path.exists() is True
    assert lock_path.exists() is True


def test_csv_write_lock_read_owner_info_handles_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_path = tmp_path / "broken.lock"
    lock_path.write_text("pid=1\n", encoding="utf-8")

    original_read_text = sink_csv_mod.Path.read_text

    def _failing_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if str(path) == str(lock_path):
            raise OSError("simulated read_text failure")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(sink_csv_mod.Path, "read_text", _failing_read_text)
    assert sink_csv_mod._read_lock_owner_info(lock_path) == {}


def test_csv_write_lock_read_owner_info_ignores_empty_keys(tmp_path: Path) -> None:
    lock_path = tmp_path / "empty_key.lock"
    lock_path.write_text("=bad\npid=1\n", encoding="utf-8")
    assert sink_csv_mod._read_lock_owner_info(lock_path) == {"pid": "1"}


def test_csv_write_lock_conflict_retries_owner_info_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "retry.csv"
    lock_path = Path(str(output_path) + ".scalim.lock")
    lock_path.write_text("held", encoding="utf-8")

    calls = {"n": 0}
    original_read_text = sink_csv_mod.Path.read_text

    def _read_text(path: Path, *args: object, **kwargs: object) -> str:
        if str(path) != str(lock_path):
            return original_read_text(path, *args, **kwargs)
        calls["n"] += 1
        if calls["n"] == 1:
            return ""
        return "pid=1\n"

    monkeypatch.setattr(sink_csv_mod.Path, "read_text", _read_text)
    monkeypatch.setattr(sink_csv_mod.time, "sleep", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match=r"lock_owner\.pid"):
        _ = sink_csv_mod._acquire_write_lock(str(output_path))


def test_csv_write_lock_release_logs_warning_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="scalim.sinks.sink_csv")
    lock_path = tmp_path / "unlink.lock"
    lock_path.write_text("pid=1\n", encoding="utf-8")

    original_unlink = sink_csv_mod.Path.unlink

    def _failing_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if str(path) == str(lock_path):
            raise OSError("simulated unlink failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(sink_csv_mod.Path, "unlink", _failing_unlink)
    sink_csv_mod._release_write_lock(lock_path)
    assert any("删除输出锁文件失败" in record.getMessage() for record in caplog.records)
