from scalim.workflow import resources_workbook as workbook_mod


def _seg(*, producer: str, decl_order: int, rows: list, header_policy: str = "once") -> object:
    return workbook_mod._WorkbookSegment(  # noqa: SLF001
        producer_node_id=str(producer),
        decl_order=int(decl_order),
        rows=list(rows),
        header_policy=str(header_policy),
    )


def test_iter_workbook_sheet_rows_header_policy_once_and_formula_escape() -> None:
    seg1 = _seg(producer="a", decl_order=0, rows=[["=1", "x"]])
    seg2 = _seg(producer="b", decl_order=1, rows=[["  +2", "@z"]])

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id", "value"], segments=[seg1, seg2])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=False))  # noqa: SLF001

    assert rows == [
        ["id", "value"],
        ["'=1", "x"],
        ["'  +2", "'@z"],
    ]


def test_iter_workbook_sheet_rows_header_policy_always_repeats_header() -> None:
    seg1 = _seg(producer="a", decl_order=0, rows=[["x"]], header_policy="always")
    seg2 = _seg(producer="b", decl_order=1, rows=[["y"]], header_policy="always")

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id"], segments=[seg1, seg2])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=True))  # noqa: SLF001

    assert rows == [
        ["id"],
        ["x"],
        ["id"],
        ["y"],
    ]


def test_iter_workbook_sheet_rows_uses_owned_aligned_rows() -> None:
    # Mapping/padding happens at apply/materialize time; commit iterates owned rows.
    seg = _seg(producer="a", decl_order=0, rows=[["x", "", ""]])

    sheet_plan = workbook_mod.SheetPlan(sheet="s", baseline_header=["id", "missing", "oob"], segments=[seg])
    rows = list(workbook_mod._iter_workbook_sheet_rows(sheet_plan, allow_formulas=True))  # noqa: SLF001

    assert rows == [
        ["id", "missing", "oob"],
        ["x", "", ""],
    ]
