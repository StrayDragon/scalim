from scalim.sinks.memory import InMemoryCsv
from scalim.workflow import resources_workbook as workbook_mod
from scalim.workflow.resources_csv import AppendSegment


def test_iter_workbook_sheet_rows_header_policy_once_and_formula_escape() -> None:
    seg1 = AppendSegment(
        decl_order=0,
        input_csv=InMemoryCsv(header=["id", "value"], rows=[["=1", "x"]]),
        header_policy="once",
        mapping=[0, 1],
        on_mismatch="error",
        align_by="strict",
        input_header=["id", "value"],
    )
    seg2 = AppendSegment(
        decl_order=1,
        input_csv=InMemoryCsv(header=["id", "value"], rows=[["  +2", "@z"]]),
        header_policy="once",
        mapping=[0, 1],
        on_mismatch="error",
        align_by="strict",
        input_header=["id", "value"],
    )

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id", "value"], segments=[seg1, seg2])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=False))

    assert rows == [
        ["id", "value"],
        ["'=1", "x"],
        ["'  +2", "'@z"],
    ]


def test_iter_workbook_sheet_rows_header_policy_always_repeats_header() -> None:
    seg1 = AppendSegment(
        decl_order=0,
        input_csv=InMemoryCsv(header=["id"], rows=[["x"]]),
        header_policy="always",
        mapping=[0],
        on_mismatch="error",
        align_by="strict",
        input_header=["id"],
    )
    seg2 = AppendSegment(
        decl_order=1,
        input_csv=InMemoryCsv(header=["id"], rows=[["y"]]),
        header_policy="always",
        mapping=[0],
        on_mismatch="error",
        align_by="strict",
        input_header=["id"],
    )

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id"], segments=[seg1, seg2])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=True))

    assert rows == [
        ["id"],
        ["x"],
        ["id"],
        ["y"],
    ]


def test_iter_workbook_sheet_rows_mapping_missing_indices_default_to_empty_string() -> None:
    seg = AppendSegment(
        decl_order=0,
        input_csv=InMemoryCsv(header=["id"], rows=[["x"]]),
        header_policy="once",
        mapping=[0, -1, 2],
        on_mismatch="error",
        align_by="strict",
        input_header=["id"],
    )

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id", "missing", "oob"], segments=[seg])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=True))

    assert rows == [
        ["id", "missing", "oob"],
        ["x", "", ""],
    ]
