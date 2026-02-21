from __future__ import annotations

from scalim.utils.graph import _stable_tie_break_key, topological_sort


def test_stable_tie_break_key_non_str_includes_type_and_repr() -> None:
    assert _stable_tie_break_key(1).startswith("int:")


def test_topological_sort_empty_input_returns_empty_list() -> None:
    assert topological_sort([], lambda _node: ()) == []
