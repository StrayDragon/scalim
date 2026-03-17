import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from scalim.dsl.by_yaml.runtime import workflow_resources as resources_mod
from scalim.events.catalog import (
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
)


class _Instrumentation:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def emit(self, event_type: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({"event_type": str(event_type), "payload": payload, "meta": dict(meta or {})})


def _write_csv(path: Path, rows: List[List[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    return path


def test_release_write_lock_is_best_effort(tmp_path: Path) -> None:
    missing = tmp_path / "missing.lock"
    resources_mod._release_write_lock(missing)

    bad_dir = tmp_path / "lockdir"
    bad_dir.mkdir()
    resources_mod._release_write_lock(bad_dir)


def test_best_effort_close_write_only_workbook_worksheets_handles_variants() -> None:
    class _NoWorksheets:
        pass

    class _BadWorksheets:
        worksheets = 123

    class _NoClosed:
        pass

    class _ClosedTrue:
        closed = True

    class _ClosedFalse:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    ws = _ClosedFalse()

    class _Workbook:
        worksheets = [_NoClosed(), _ClosedTrue(), ws]

    resources_mod._best_effort_close_write_only_workbook_worksheets(_NoWorksheets())
    resources_mod._best_effort_close_write_only_workbook_worksheets(_BadWorksheets())
    resources_mod._best_effort_close_write_only_workbook_worksheets(_Workbook())
    assert ws.closed is True


def test_read_csv_header_errors(tmp_path: Path) -> None:
    with pytest.raises(resources_mod.WorkflowWriteError, match="Missing input CSV"):
        _ = resources_mod._read_csv_header(str(tmp_path / "nope.csv"))

    empty = _write_csv(tmp_path / "empty.csv", [])
    with pytest.raises(resources_mod.WorkflowWriteError, match="empty"):
        _ = resources_mod._read_csv_header(str(empty))

    invalid = _write_csv(tmp_path / "invalid.csv", [["", "ok"], ["x", "y"]])
    with pytest.raises(resources_mod.WorkflowWriteError, match="invalid header"):
        _ = resources_mod._read_csv_header(str(invalid))


def test_resource_manager_unknown_resource_ids_raise(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
    )

    csv_path = _write_csv(tmp_path / "input.csv", [["id"], ["a"]])
    with pytest.raises(resources_mod.WorkflowWriteError, match="Unknown workbook resource id"):
        manager.apply_workbook_sheet(
            workflow_node_id="n",
            workbook_id="nope",
            sheet="S",
            input_node_id="a",
            input_output_id="out",
            input_csv_path=str(csv_path),
            on_conflict="error",
        )

    with pytest.raises(resources_mod.WorkflowWriteError, match="Unknown csv resource id"):
        manager.apply_csv_append(
            workflow_node_id="n",
            csv_id="nope",
            input_node_id="a",
            input_output_id="out",
            input_csv_path=str(csv_path),
            header_policy="once",
            on_mismatch="error",
        )


def test_resource_manager_workbook_append_mismatch_error_warn_skip(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    workbook_path = tmp_path / "report.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
    )

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    mismatch = _write_csv(tmp_path / "b.csv", [["id", "other"], ["a1", "A1"]])

    manager.apply_workbook_append(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="Field alignment mismatch"):
        manager.apply_workbook_append(
            workflow_node_id="n1",
            workbook_id="report",
            sheet="S",
            input_node_id="b",
            input_output_id="detail",
            input_csv_path=str(mismatch),
            align_by="field_id",
            header_policy="once",
            on_mismatch="error",
        )
    manager.discard_all(workflow_node_id="n_discard", reason="test")

    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(tmp_path / "warn.xlsx")},
        csv_defs={},
    )
    manager.apply_workbook_append(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_workbook_append(
        workflow_node_id="n1",
        workbook_id="report",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(mismatch),
        align_by="field_id",
        header_policy="once",
        on_mismatch="warn",
    )
    assert [e for e in instrumentation.events if e["event_type"] == EVENT_DIAGNOSTIC_WARNING]
    manager.discard_all(workflow_node_id="n_discard", reason="test")

    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(tmp_path / "skip.xlsx")},
        csv_defs={},
    )
    manager.apply_workbook_append(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_workbook_append(
        workflow_node_id="n1",
        workbook_id="report",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(mismatch),
        align_by="field_id",
        header_policy="once",
        on_mismatch="skip",
    )
    skip_events = [e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_WRITE and e["payload"].action == "skip"]
    assert skip_events
    manager.discard_all(workflow_node_id="n_discard", reason="test")


def test_resource_manager_csv_append_mismatch_error_and_discard(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    csv_path = tmp_path / "merged.csv"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={"merged": str(csv_path)},
    )

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    mismatch = _write_csv(tmp_path / "b.csv", [["id", "other"], ["a1", "A1"]])

    manager.apply_csv_append(
        workflow_node_id="n0",
        csv_id="merged",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="Field alignment mismatch"):
        manager.apply_csv_append(
            workflow_node_id="n1",
            csv_id="merged",
            input_node_id="b",
            input_output_id="detail",
            input_csv_path=str(mismatch),
            header_policy="once",
            on_mismatch="error",
        )

    manager.discard_all(workflow_node_id="n_discard", reason="test")
    assert [e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_DISCARD and e["payload"].resource_type == "csv"]


def test_resource_manager_commit_all_releases_locks_when_no_segments(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()

    workbook_path = tmp_path / "empty.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
    )
    _ = manager._get_or_create_workbook("report", workflow_node_id="n")  # noqa: SLF001
    assert Path(str(workbook_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    manager.commit_all()
    assert not Path(str(workbook_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    assert not workbook_path.exists()

    csv_output_path = tmp_path / "empty.csv"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=_Instrumentation(),
        workbook_defs={},
        csv_defs={"merged": str(csv_output_path)},
    )
    _ = manager._get_or_create_csv("merged", workflow_node_id="n")  # noqa: SLF001
    assert Path(str(csv_output_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    manager.commit_all()
    assert not Path(str(csv_output_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    assert not csv_output_path.exists()


def test_resource_manager_commit_workbook_handles_missing_sheet_plan(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    workbook_path = tmp_path / "report.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
    )

    csv_path = _write_csv(tmp_path / "input.csv", [["id"], ["a1"]])
    manager.apply_workbook_sheet(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(csv_path),
        on_conflict="error",
    )

    plan = manager._workbooks["report"]  # noqa: SLF001
    plan.sheet_order.insert(0, "MISSING")

    manager.commit_all()
    assert workbook_path.exists()
    assert not Path(str(workbook_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()


def test_resource_manager_commit_workbook_commit_failure_raises(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(output_dir)},
        csv_defs={},
    )

    csv_path = _write_csv(tmp_path / "input.csv", [["id"], ["a1"]])
    manager.apply_workbook_sheet(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(csv_path),
        on_conflict="error",
    )

    with pytest.raises(resources_mod.WorkflowWriteError, match="Workbook commit failed"):
        manager.commit_all()
    assert not Path(str(output_dir) + resources_mod._WRITE_LOCK_SUFFIX).exists()


def test_resource_manager_commit_csv_commit_failure_raises(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    output_dir = tmp_path / "csv_out"
    output_dir.mkdir()

    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={"merged": str(output_dir)},
    )

    csv_path = _write_csv(tmp_path / "input.csv", [["id"], ["a1"]])
    manager.apply_csv_append(
        workflow_node_id="n0",
        csv_id="merged",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(csv_path),
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="CSV commit failed"):
        manager.commit_all()
    assert not Path(str(output_dir) + resources_mod._WRITE_LOCK_SUFFIX).exists()


def test_resource_manager_commit_workbook_missing_openpyxl_releases_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    instrumentation = _Instrumentation()
    workbook_path = tmp_path / "report.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
    )

    csv_path = _write_csv(tmp_path / "input.csv", [["id"], ["a1"]])
    manager.apply_workbook_sheet(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(csv_path),
        on_conflict="error",
    )

    def _raise_import_error(*args: object, **kwargs: object) -> object:
        raise ImportError("missing openpyxl")

    monkeypatch.setattr(resources_mod, "require_optional_dependency", _raise_import_error)
    with pytest.raises(resources_mod.WorkflowWriteError, match="missing openpyxl"):
        manager.commit_all()
    assert not Path(str(workbook_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    assert not workbook_path.exists()
