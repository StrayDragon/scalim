import csv
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from scalim.dsl.by_yaml.runtime import workflow_resources as resources_mod
from scalim.dsl.by_yaml.runtime import workflow_resources_sheetbook as resources_sheetbook_mod
from scalim.dsl.by_yaml.runtime import workflow_resources_workbook as resources_workbook_mod
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
        sheetbook_defs={},
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

    with pytest.raises(resources_mod.WorkflowWriteError, match="Unknown sheetbook resource id"):
        manager.apply_sheetbook_sheet(
            workflow_node_id="n",
            sheetbook_id="nope",
            sheet="S",
            input_node_id="a",
            input_output_id="out",
            input_csv_path=str(csv_path),
            on_conflict="error",
        )


def test_resource_manager_workbook_append_mismatch_error_warn_skip(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    workbook_path = tmp_path / "report.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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


def test_resource_manager_sheetbook_sheet_conflict_skip_error_overwrite(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    second = _write_csv(tmp_path / "b.csv", [["id", "value"], ["b1", "B1"]])

    manager.apply_sheetbook_sheet(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        on_conflict="error",
    )

    manager.apply_sheetbook_sheet(
        workflow_node_id="n1",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(second),
        on_conflict="skip",
    )
    assert [e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_WRITE and e["payload"].action == "skip"]

    with pytest.raises(resources_mod.WorkflowWriteError, match="Sheet conflict"):
        manager.apply_sheetbook_sheet(
            workflow_node_id="n2",
            sheetbook_id="sb",
            sheet="S",
            input_node_id="b",
            input_output_id="detail",
            input_csv_path=str(second),
            on_conflict="error",
        )

    manager.apply_sheetbook_sheet(
        workflow_node_id="n3",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="c",
        input_output_id="detail",
        input_csv_path=str(second),
        on_conflict="overwrite",
    )
    overwrite_events = [
        e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_WRITE and e["payload"].action == "overwrite"
    ]
    assert overwrite_events

    rows = list(
        manager.iter_sheetbook_sheet_rows(
            consumer_node_id="consumer",
            visible_producer_node_ids=frozenset(),
            producer_node_id="c",
            sheetbook_id="sb",
            sheet="S",
        )
    )
    assert rows == [{"id": "b1", "value": "B1"}]


def test_resource_manager_sheetbook_append_mismatch_error_warn_skip_and_budget(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    mismatch = _write_csv(tmp_path / "b.csv", [["id", "other"], ["b1", "B1"]])

    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="Field alignment mismatch"):
        manager.apply_sheetbook_append(
            workflow_node_id="n1",
            sheetbook_id="sb",
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
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n1",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(mismatch),
        align_by="header",
        header_policy="once",
        on_mismatch="warn",
    )
    assert [e for e in instrumentation.events if e["event_type"] == EVENT_DIAGNOSTIC_WARNING]
    manager.discard_all(workflow_node_id="n_discard", reason="test")

    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n1",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(mismatch),
        align_by="header",
        header_policy="once",
        on_mismatch="skip",
    )
    skip_events = [e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_WRITE and e["payload"].action == "skip"]
    assert skip_events
    manager.discard_all(workflow_node_id="n_discard", reason="test")

    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=1,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S1",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="max_sheets"):
        manager.apply_sheetbook_append(
            workflow_node_id="n1",
            sheetbook_id="sb",
            sheet="S2",
            input_node_id="b",
            input_output_id="detail",
            input_csv_path=str(first),
            align_by="field_id",
            header_policy="once",
            on_mismatch="error",
        )
    manager.discard_all(workflow_node_id="n_discard", reason="test")


def test_resource_manager_sheetbook_append_duplicate_producer_is_rejected(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )
    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])

    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    with pytest.raises(resources_mod.WorkflowWriteError, match="Duplicate sheetbook write"):
        manager.apply_sheetbook_append(
            workflow_node_id="n1",
            sheetbook_id="sb",
            sheet="S",
            input_node_id="a",
            input_output_id="detail",
            input_csv_path=str(first),
            align_by="field_id",
            header_policy="once",
            on_mismatch="error",
        )


def test_workflow_resource_manager_emit_does_not_deadlock_on_reentry(tmp_path: Path) -> None:
    class _ReentrantInstrumentation:
        def __init__(self) -> None:
            self._reentered = False
            self.manager = None
            self.csv_input_path = None

        def emit(self, event_type: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> None:
            _ = event_type, meta
            if self._reentered:
                return
            if str(event_type) != EVENT_WORKFLOW_RESOURCE_WRITE:
                return
            if getattr(payload, "action", None) != "skip":
                return
            self._reentered = True
            self.manager.apply_csv_append(  # type: ignore[union-attr]
                workflow_node_id="reentry",
                csv_id="merged",
                input_node_id="r",
                input_output_id="out",
                input_csv_path=str(self.csv_input_path),  # type: ignore[arg-type]
                header_policy="once",
                on_mismatch="error",
            )

    instrumentation = _ReentrantInstrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(tmp_path / "report.xlsx")},
        csv_defs={"merged": str(tmp_path / "merged.csv")},
        sheetbook_defs={},
    )
    instrumentation.manager = manager

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    instrumentation.csv_input_path = str(first)

    manager.apply_workbook_sheet(
        workflow_node_id="n0",
        workbook_id="report",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        on_conflict="error",
    )

    runner = threading.Thread(
        target=lambda: manager.apply_workbook_sheet(
            workflow_node_id="n1",
            workbook_id="report",
            sheet="S",
            input_node_id="b",
            input_output_id="detail",
            input_csv_path=str(first),
            on_conflict="skip",
        ),
        daemon=True,
    )
    runner.start()
    runner.join(timeout=1.0)
    if runner.is_alive():
        pytest.fail("WorkflowResourceManager.emit appears to be called under internal locks (reentry deadlock)")
    assert instrumentation._reentered is True


def test_resource_manager_sheetbook_iter_rows_visibility_and_errors(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=None,
                export_write_lock=False,
            )
        },
    )

    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    second = _write_csv(tmp_path / "b.csv", [["id", "value"], ["b1", "B1"]])

    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n1",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="b",
        input_output_id="detail",
        input_csv_path=str(second),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    rows = list(
        manager.iter_sheetbook_sheet_rows(
            consumer_node_id="consumer",
            visible_producer_node_ids=frozenset(),
            producer_node_id="b",
            sheetbook_id="sb",
            sheet="S",
        )
    )
    assert rows == [{"id": "b1", "value": "B1"}]

    with pytest.raises(ValueError, match="Unknown sheetbook resource id"):
        _ = list(
            manager.iter_sheetbook_sheet_rows(
                consumer_node_id="consumer",
                visible_producer_node_ids=frozenset(),
                producer_node_id="a",
                sheetbook_id="nope",
                sheet="S",
            )
        )

    with pytest.raises(ValueError, match="Unknown sheetbook sheet"):
        _ = list(
            manager.iter_sheetbook_sheet_rows(
                consumer_node_id="consumer",
                visible_producer_node_ids=frozenset(),
                producer_node_id="a",
                sheetbook_id="sb",
                sheet="Other",
            )
        )

    with pytest.raises(ValueError, match="Unknown sheetbook ref node"):
        _ = list(
            manager.iter_sheetbook_sheet_rows(
                consumer_node_id="consumer",
                visible_producer_node_ids=frozenset(),
                producer_node_id="nope",
                sheetbook_id="sb",
                sheet="S",
            )
        )


def test_resource_manager_sheetbook_commit_import_error_and_save_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    export_path = tmp_path / "report.xlsx"
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=str(export_path),
                export_write_lock=True,
            )
        },
    )
    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    def _raise_import(*_args: object, **_kwargs: object) -> Any:  # noqa: ANN401
        raise ImportError("no openpyxl")

    monkeypatch.setattr(resources_workbook_mod, "require_optional_dependency", _raise_import)
    with pytest.raises(resources_mod.WorkflowWriteError, match="openpyxl"):
        manager.commit_all()
    assert not Path(str(export_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()

    class _FakeWS:
        def append(self, row: List[object]) -> None:
            _ = row

    class _FakeWB:
        def __init__(self, write_only: bool = True) -> None:
            _ = write_only

        def create_sheet(self, name: str) -> _FakeWS:
            _ = name
            return _FakeWS()

        def save(self, path: Path) -> None:
            path.write_text("tmp", encoding="utf-8")
            raise RuntimeError("boom")

        def close(self) -> None:
            return

    export_path2 = tmp_path / "report2.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=str(export_path2),
                export_write_lock=False,
            )
        },
    )
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    temp_path = tmp_path / "temp.xlsx.tmp"
    monkeypatch.setattr(
        resources_workbook_mod,
        "require_optional_dependency",
        lambda *_args, **_kwargs: type("_M", (), {"Workbook": _FakeWB})(),
    )
    monkeypatch.setattr(resources_sheetbook_mod, "create_temp_path", lambda _path, _suffix: str(temp_path))
    with pytest.raises(resources_mod.WorkflowWriteError, match="Sheetbook export failed"):
        manager.commit_all()
    assert not temp_path.exists()


def test_resource_manager_sheetbook_discard_releases_lock_if_present(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": resources_mod.SheetBookDef(
                resource_id="sb",
                budget_max_sheets=4,
                budget_max_total_cells=1000,
                export_path=str(tmp_path / "report.xlsx"),
                export_write_lock=True,
            )
        },
    )
    first = _write_csv(tmp_path / "a.csv", [["id", "value"], ["a1", "A1"]])
    manager.apply_sheetbook_append(
        workflow_node_id="n0",
        sheetbook_id="sb",
        sheet="S",
        input_node_id="a",
        input_output_id="detail",
        input_csv_path=str(first),
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    plan = manager._sheetbooks["sb"]
    lock_path = tmp_path / "forced.lock"
    lock_path.write_text("lock", encoding="utf-8")
    plan.lock_path = lock_path

    manager.discard_all(workflow_node_id="n_discard", reason="test")
    assert not lock_path.exists()
    assert [e for e in instrumentation.events if e["event_type"] == EVENT_WORKFLOW_RESOURCE_DISCARD]


def test_resource_manager_commit_all_releases_locks_when_no_segments(tmp_path: Path) -> None:
    instrumentation = _Instrumentation()

    workbook_path = tmp_path / "empty.xlsx"
    manager = resources_mod.WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        workbook_defs={"report": str(workbook_path)},
        csv_defs={},
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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
        sheetbook_defs={},
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

    monkeypatch.setattr(resources_workbook_mod, "require_optional_dependency", _raise_import_error)
    with pytest.raises(resources_mod.WorkflowWriteError, match="missing openpyxl"):
        manager.commit_all()
    assert not Path(str(workbook_path) + resources_mod._WRITE_LOCK_SUFFIX).exists()
    assert not workbook_path.exists()
