import pytest

from scalim.workflow import resources_sheetbook as sheetbook_mod


@pytest.mark.parametrize(
    ("expected", "actual", "align_by", "on_mismatch", "action"),
    [
        (["a", "b"], ["a", "b"], "strict", "error", "ok"),
        (["a", "b"], ["b", "a"], "field_id", "error", "ok"),
        (["a", "b"], ["b", "a"], "strict", "warn", "warn"),
        (["a", "b"], ["b"], "strict", "skip", "skip"),
    ],
)
def test_sheetbook_decide_alignment_action_matrix(
    expected: object,
    actual: object,
    align_by: str,
    on_mismatch: str,
    action: str,
) -> None:
    resolved = sheetbook_mod._sheetbook_decide_alignment_action(expected, actual, align_by=align_by, on_mismatch=on_mismatch)
    assert resolved == action


def test_sheetbook_visible_segments_cutoff_and_visibility_filtering() -> None:
    s1 = sheetbook_mod.SheetBookSegment(producer_node_id="p1", decl_order=0, rows=[[1]], header_policy="once")
    s2 = sheetbook_mod.SheetBookSegment(producer_node_id="p2", decl_order=1, rows=[[2]], header_policy="once")
    s3 = sheetbook_mod.SheetBookSegment(producer_node_id="p3", decl_order=2, rows=[[3]], header_policy="once")

    ordered = [s1, s2, s3]
    cutoff = sheetbook_mod._sheetbook_find_cutoff_index(ordered, producer_node_id="p2")
    assert cutoff == 1

    visible_segments = sheetbook_mod._sheetbook_collect_visible_segments(
        ordered,
        cutoff_idx=int(cutoff),
        producer_node_id="p2",
        visible_producer_node_ids=frozenset({"p1"}),
    )
    assert [producer for producer, _rows in visible_segments] == ["p1", "p2"]

    rows = list(sheetbook_mod._iter_sheetbook_row_dicts(["x"], visible_segments))
    assert rows == [{"x": 1}, {"x": 2}]
