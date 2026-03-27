from scalim._internal.utils.iterables import ordered_unique_str


def test_ordered_unique_str_removes_duplicates_while_preserving_order() -> None:
    assert ordered_unique_str(["a", "a", "b"]) == ("a", "b")


def test_ordered_unique_str_normalizes_items_via_str() -> None:
    assert ordered_unique_str(["1", 1, 2, "2", "1"]) == ("1", "2")
