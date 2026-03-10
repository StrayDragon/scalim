import pytest

from scalim.spec.ir.sources import SourceNormalizeIr


def test_source_normalize_index_by_key_success() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 2, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "a"
    assert result[2]["v"] == "b"


def test_source_normalize_index_by_key_duplicate_error() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(ValueError, match="duplicate key"):
        _ = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")


def test_source_normalize_index_by_key_duplicate_first() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="first")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "a"


def test_source_normalize_index_by_key_duplicate_last() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="last")
    result = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")
    assert result[1]["v"] == "b"


def test_source_normalize_unknown_kind_rejected() -> None:
    normalize = SourceNormalizeIr(kind="unknown", key_field="id")
    with pytest.raises(ValueError, match="Unknown normalize\\.kind"):
        _ = normalize.apply([], source_id="s1")


def test_source_normalize_index_by_key_accepts_mapping_passthrough() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    mapping = {1: {"id": 1, "v": "a"}}
    assert normalize.apply(mapping, source_id="s1") is mapping


def test_source_normalize_index_by_key_rejects_non_list_result() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="expected loader result list\\[row\\]"):
        _ = normalize.apply("not-a-list", source_id="s1")


def test_source_normalize_index_by_key_rejects_non_mapping_row() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="row is a Mapping"):
        _ = normalize.apply([1], source_id="s1")


def test_source_normalize_index_by_key_rejects_missing_key_field_in_row() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(KeyError, match="missing key_field"):
        _ = normalize.apply([{"other": 1}], source_id="s1")


def test_source_normalize_index_by_key_rejects_none_key_value() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(ValueError, match="is None"):
        _ = normalize.apply([{"id": None}], source_id="s1")


def test_source_normalize_index_by_key_rejects_invalid_on_conflict() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id", on_conflict="bad")
    with pytest.raises(ValueError, match="invalid on_conflict"):
        _ = normalize.apply([{"id": 1, "v": "a"}, {"id": 1, "v": "b"}], source_id="s1")


def test_source_normalize_index_by_key_rejects_unhashable_key_value() -> None:
    normalize = SourceNormalizeIr(kind="index_by_key", key_field="id")
    with pytest.raises(TypeError, match="must be hashable"):
        _ = normalize.apply([{"id": []}], source_id="s1")
