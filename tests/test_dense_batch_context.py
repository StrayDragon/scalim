import pytest

from scalim.execution.adaptive.overlay_context import OverlayBatchContext
from scalim.execution.context import BatchContext, DenseBatchContext, create_batch_context_for_rows


def test_create_batch_context_for_rows_falls_back_for_non_contiguous() -> None:
    ctx = create_batch_context_for_rows([0, 2, 3])
    assert isinstance(ctx, BatchContext)
    assert not isinstance(ctx, DenseBatchContext)


def test_create_batch_context_for_rows_falls_back_for_empty_and_non_ints() -> None:
    assert isinstance(create_batch_context_for_rows([]), BatchContext)
    assert isinstance(create_batch_context_for_rows(["x"]), BatchContext)
    assert isinstance(create_batch_context_for_rows([0, "x"]), BatchContext)


def test_create_batch_context_for_rows_uses_dense_for_contiguous_ints() -> None:
    ctx = create_batch_context_for_rows([10, 11, 12])
    assert isinstance(ctx, DenseBatchContext)


def test_dense_batch_context_set_get_delete_and_keys() -> None:
    ctx = DenseBatchContext(base_row_id=5, row_count=3)
    ctx.set_field_value("a", 5, 1)
    ctx.set_field_value("a", 6, None)
    ctx.set_field_value("b", 7, "x")

    assert ctx.get_field_value("a", 5) == 1
    assert ctx.get_field_value("a", 6) is None
    assert ctx.get_field_value("a", 7) is None
    assert ctx.get_field_value("a", 7, default="d") == "d"
    assert ctx.get_field_value("a", "x", default="d") == "d"
    assert ctx.has_field("a")
    assert ctx.get_field_count() == 2

    ctx.delete_row_from_field("a", 5)
    assert ctx.get_field_value("a", 5) is None
    assert ctx.get_field_value("a", 6) is None
    assert ctx.has_field("a")

    ctx.delete_row_from_field("a", 6)
    assert not ctx.has_field("a")
    assert ctx.get_field_keys() == {"b"}


def test_dense_batch_context_delete_row_from_all_fields_respects_exclude() -> None:
    ctx = DenseBatchContext(base_row_id=0, row_count=2)
    ctx.set_field_value("a", 0, 1)
    ctx.set_field_value("b", 0, 2)
    ctx.set_field_value("b", 1, 3)

    released = ctx.delete_row_from_all_fields(0, exclude_fields={"b"})
    assert released == ["a"]
    assert ctx.get_field_value("a", 0) is None
    assert ctx.get_field_value("b", 0) == 2


def test_dense_batch_context_delete_row_from_field_early_returns() -> None:
    ctx = DenseBatchContext(base_row_id=0, row_count=2)
    ctx.delete_row_from_field("missing", 0)

    ctx.set_field_value("a", 1, 1)
    ctx.delete_row_from_field("a", "x")
    ctx.delete_row_from_field("a", 0)
    assert ctx.get_field_value("a", 1) == 1


def test_dense_batch_context_delete_row_from_all_fields_handles_idx_none_and_present_zero() -> None:
    ctx = DenseBatchContext(base_row_id=0, row_count=2)
    ctx.set_field_value("a", 1, 1)
    assert ctx.delete_row_from_all_fields("x") == []
    assert ctx.delete_row_from_all_fields(0) == []


def test_dense_batch_context_required_fields_and_disable_row() -> None:
    ctx = DenseBatchContext(base_row_id=0, row_count=1, required_fields={"keep"})
    ctx.set_field_value("drop", 0, 1)
    assert ctx.get_field_count() == 0

    ctx.set_field_value("keep", 0, 1)
    assert ctx.get_field_value("keep", 0) == 1

    ctx.disable_row(0)
    ctx.set_field_value("keep", 0, 2)
    assert ctx.get_field_value("keep", 0) == 1


def test_dense_batch_context_get_all_rows_for_field_and_clear() -> None:
    ctx = DenseBatchContext(base_row_id=3, row_count=3)
    ctx.set_field_value("a", 3, 1)
    ctx.set_field_value("a", 5, 2)
    assert ctx.get_all_rows_for_field("missing") == set()
    assert ctx.get_all_rows_for_field("a") == {3, 5}

    ctx.delete_row_from_field("a", 3)
    assert ctx.get_all_rows_for_field("a") == {5}

    ctx.disable_row(5)
    ctx.clear()
    assert ctx.get_field_count() == 0
    assert ctx.get_field_keys() == set()


def test_dense_batch_context_set_out_of_range_raises() -> None:
    ctx = DenseBatchContext(base_row_id=0, row_count=1)
    with pytest.raises(ValueError, match="row_id"):
        ctx.set_field_value("a", 99, 1)


def test_overlay_context_reads_fall_back_to_dense_base() -> None:
    base = DenseBatchContext(base_row_id=0, row_count=2)
    base.set_field_value("a", 0, 1)

    overlay = OverlayBatchContext(base, required_fields=None)
    assert overlay.get_field_value("a", 0) == 1

    overlay.set_field_value("a", 1, 2)
    assert overlay.get_field_value("a", 1) == 2
    assert base.get_field_value("a", 1) is None

    assert overlay.get_field_keys() == {"a"}
    assert overlay.get_field_count() == 1


def test_batch_context_clear_clears_disabled_rows() -> None:
    ctx = BatchContext()
    ctx.disable_row(0)
    ctx.set_field_value("a", 0, 1)
    assert ctx.get_field_value("a", 0) is None

    ctx.clear()
    ctx.set_field_value("a", 0, 1)
    assert ctx.get_field_value("a", 0) == 1
