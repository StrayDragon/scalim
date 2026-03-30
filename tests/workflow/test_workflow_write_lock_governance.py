import os
import time
from pathlib import Path

import pytest

from scalim.workflow import resources_base as resources_base_mod


def test_write_lock_conflict_includes_owner_info_and_hint(tmp_path: Path) -> None:
    output_path = tmp_path / "out.xlsx"

    lock_path = resources_base_mod.acquire_write_lock(
        str(output_path),
        owner={"workflow_exec_id": "wf", "resource_type": "workbook", "resource_id": "report"},
    )
    try:
        text = lock_path.read_text(encoding="utf-8")
        assert "workflow_exec_id=wf" in text
        assert "resource_type=workbook" in text
        assert "resource_id=report" in text

        with pytest.raises(resources_base_mod.ScalimWorkflowWriteError) as excinfo:
            _ = resources_base_mod.acquire_write_lock(
                str(output_path),
                owner={"workflow_exec_id": "wf2"},
            )
        diff = excinfo.value.diff or []
        assert any("lock_owner.workflow_exec_id='wf'" in str(x) for x in diff)
        assert any("lock_owner.resource_type='workbook'" in str(x) for x in diff)
        assert any("lock_owner.resource_id='report'" in str(x) for x in diff)
        assert any("hint=delete_lock_file_if_safe" in str(x) for x in diff)
    finally:
        resources_base_mod.release_write_lock(lock_path)
        assert not lock_path.exists()


def test_write_lock_force_unlinks_stale_lock_and_reacquires(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    lock_path = Path(str(output_path) + resources_base_mod.WRITE_LOCK_SUFFIX)
    lock_path.write_text("pid=1\nworkflow_exec_id=stale\n", encoding="utf-8")
    stale_ts = time.time() - 5.0
    os.utime(str(lock_path), (stale_ts, stale_ts))

    new_lock = resources_base_mod.acquire_write_lock(
        str(output_path),
        owner={"workflow_exec_id": "wf"},
        stale_after_s=0.1,
        force=True,
    )
    try:
        assert new_lock.exists()
        text = new_lock.read_text(encoding="utf-8")
        assert "workflow_exec_id=wf" in text
        assert "workflow_exec_id=stale" not in text
    finally:
        resources_base_mod.release_write_lock(new_lock)


def test_read_lock_owner_info_missing_file_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lock"
    info, mtime_s = resources_base_mod._read_lock_owner_info(missing)  # noqa: SLF001
    assert info == {}
    assert mtime_s is None


def test_read_lock_owner_info_handles_stat_oserror_and_empty_keys() -> None:
    class _FakePath:
        def stat(self):  # noqa: ANN001
            raise OSError("boom")

        def read_text(self, encoding: str = "utf-8") -> str:  # noqa: ARG002
            return "=x\nk=v\n"

    info, mtime_s = resources_base_mod._read_lock_owner_info(_FakePath())  # type: ignore[arg-type]  # noqa: SLF001
    assert info == {"k": "v"}
    assert mtime_s is None


def test_read_lock_owner_info_handles_bad_mtime_and_unreadable_file() -> None:
    class _FakeStat:
        st_mtime = "not-a-float"

    class _FakePath:
        def __init__(self, *, readable: bool) -> None:
            self._readable = bool(readable)

        def stat(self) -> _FakeStat:  # noqa: ANN001
            return _FakeStat()

        def read_text(self, encoding: str = "utf-8") -> str:  # noqa: ARG002
            if not self._readable:
                raise OSError("boom")
            return "pid=1\nk=v\n"

    info, mtime_s = resources_base_mod._read_lock_owner_info(_FakePath(readable=True))  # type: ignore[arg-type]  # noqa: SLF001
    assert info.get("k") == "v"
    assert mtime_s is None

    info2, mtime_s2 = resources_base_mod._read_lock_owner_info(_FakePath(readable=False))  # type: ignore[arg-type]  # noqa: SLF001
    assert info2 == {}
    assert mtime_s2 is None


def test_write_lock_rejects_invalid_stale_after_s(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    with pytest.raises(ValueError, match="stale_after_s"):
        _ = resources_base_mod.acquire_write_lock(str(output_path), stale_after_s=-1.0)


def test_write_lock_conflict_includes_stale_after_and_force_in_diff(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    lock_path = resources_base_mod.acquire_write_lock(str(output_path))
    try:
        with pytest.raises(resources_base_mod.ScalimWorkflowWriteError) as excinfo:
            _ = resources_base_mod.acquire_write_lock(
                str(output_path),
                stale_after_s=3600.0,
                force=True,
            )
        diff = excinfo.value.diff or []
        assert any("stale_after_s=" in str(x) for x in diff)
        assert any("force=True" in str(x) for x in diff)
    finally:
        resources_base_mod.release_write_lock(lock_path)


def test_write_lock_owner_empty_key_is_skipped(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    lock_path = resources_base_mod.acquire_write_lock(str(output_path), owner={"": "x", "ok": "1"})
    try:
        text = lock_path.read_text(encoding="utf-8")
        assert "ok=1" in text
        assert "\n=x\n" not in text
    finally:
        resources_base_mod.release_write_lock(lock_path)
