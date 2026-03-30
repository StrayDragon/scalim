from scalim.execution.adaptive.overlay_context import OverlayBatchContext
from scalim.execution.context import BatchContext


def test_overlay_batch_context_reads_writes_and_deletes_and_drains() -> None:
    base = BatchContext()
    base.set_field_value("a", 0, 1)
    base.set_field_value("a", 1, 2)
    base.set_field_value("b", 0, 10)

    overlay = OverlayBatchContext(base, required_fields={"a", "c"})

    # Write is filtered by required_fields.
    overlay.set_field_value("b", 0, 999)
    assert overlay.drain_overlay() == {}

    # Reads fall back to base when not present in overlay.
    assert overlay.get_field_value("b", 0) == 10
    assert overlay.has_field("b") is True
    assert overlay.has_field("missing") is False

    # Writes go to overlay only.
    overlay.set_field_value("c", 0, 3)
    overlay.set_field_value("a", 0, 100)
    assert overlay.get_field_value("a", 0) == 100
    assert overlay.get_field_value("a", 1) == 2
    assert overlay.has_field("a") is True
    assert overlay.has_field("c") is True

    assert overlay.get_field_values_for_row(0, ["a", "b", "c"]) == {"a": 100, "b": 10, "c": 3}

    # Deleting row entries never affects base.
    overlay.delete_row_from_field("a", 0)
    assert overlay.get_field_value("a", 0) == 1

    overlay.set_field_value("a", 0, 111)
    overlay.delete_row_from_all_fields(0, exclude_fields={"c"})
    assert overlay.get_field_value("a", 0) == 1
    assert overlay.get_field_value("c", 0) == 3

    overlay.set_field_value("a", 1, 222)
    overlay.set_field_value("c", 1, 444)
    overlay.delete_row_from_all_fields(1)
    assert overlay.get_field_value("a", 1) == 2
    assert overlay.get_field_value("c", 1, default=None) is None

    # delete_field only removes overlay state.
    overlay.delete_field("c")
    assert overlay.get_field_value("c", 0, default=None) is None

    overlay.set_field_value("a", 2, 999)
    assert overlay.get_all_rows_for_field("a") == {0, 1, 2}
    assert overlay.get_all_rows_for_field("b") == {0}
    assert overlay.get_field_keys() == {"a", "b"}
    assert overlay.get_field_count() == 2

    drained = overlay.drain_overlay()
    assert drained == {"a": {2: 999}}
    assert overlay.drain_overlay() == {}

    overlay.set_field_value("a", 0, 123)
    overlay.clear()
    assert overlay.drain_overlay() == {}
