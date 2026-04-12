from pathlib import Path
from typing import Any, Dict, Optional

from scalim.sinks import InMemoryCsv
from scalim.workflow.resources import WorkflowResourceManager
from scalim.workflow.resources_sheetbook import SheetBookDef


class _Instrumentation:
    def emit(self, event_type: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> None:
        _ = event_type, payload, meta


def test_workbook_sheet_decl_order_is_updated_when_first_touch_is_out_of_order(tmp_path: Path) -> None:
    inst = _Instrumentation()
    out_path = tmp_path / "out.xlsx"
    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=inst,
        workbook_defs={"wb": str(out_path)},
        csv_defs={},
        sheetbook_defs={},
    )
    input_csv = InMemoryCsv(header=["a"], rows=[["1"]])

    manager.apply_workbook_append(
        workflow_node_id="w2",
        decl_order=2,
        workbook_id="wb",
        sheet="S",
        input_node_id="n2",
        input_output_id="o",
        input_csv=input_csv,
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_workbook_append(
        workflow_node_id="w1",
        decl_order=1,
        workbook_id="wb",
        sheet="S",
        input_node_id="n1",
        input_output_id="o",
        input_csv=input_csv,
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    plan = manager._workbooks["wb"]  # noqa: SLF001
    assert int(plan.sheet_decl_order["S"]) == 1


def test_sheetbook_sheet_decl_order_is_updated_when_first_touch_is_out_of_order(tmp_path: Path) -> None:
    inst = _Instrumentation()
    manager = WorkflowResourceManager(
        workflow_exec_id="wf",
        instrumentation=inst,
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={
            "sb": SheetBookDef(
                resource_id="sb",
                budget_max_sheets=10,
                budget_max_total_cells=10000,
                export_path=None,
            )
        },
    )
    input_csv = InMemoryCsv(header=["a"], rows=[["1"]])

    manager.apply_sheetbook_append(
        workflow_node_id="w2",
        decl_order=2,
        sheetbook_id="sb",
        sheet="S",
        input_node_id="n2",
        input_output_id="o",
        input_csv=input_csv,
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )
    manager.apply_sheetbook_append(
        workflow_node_id="w1",
        decl_order=1,
        sheetbook_id="sb",
        sheet="S",
        input_node_id="n1",
        input_output_id="o",
        input_csv=input_csv,
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
    )

    plan = manager._sheetbooks["sb"]  # noqa: SLF001
    assert int(plan.sheet_decl_order["S"]) == 1
