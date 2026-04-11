import pytest

from scalim._internal.type_narrowing import as_list, as_mapping, mapping_get_str, require_str


def test_as_mapping_narrows_dict_and_rejects_non_dict() -> None:
    mapping = {"k": 1}
    assert as_mapping(mapping, path="p") is mapping
    assert as_mapping([], path="p") is None


def test_as_list_narrows_list_and_rejects_non_list() -> None:
    items = [1, 2]
    assert as_list(items, path="p") is items
    assert as_list({}, path="p") is None


def test_require_str_returns_str_and_raises_type_error() -> None:
    assert require_str("x", path="p") == "x"
    with pytest.raises(TypeError, match=r"^p must be a string, got 'int'$"):
        _ = require_str(1, path="p")


def test_mapping_get_str_returns_optional_str_and_raises_on_wrong_type() -> None:
    mapping = {
        "ok": "v",
        "none": None,
        "bad": 123,
    }
    assert mapping_get_str(mapping, "missing", path="p") is None
    assert mapping_get_str(mapping, "none", path="p") is None
    assert mapping_get_str(mapping, "ok", path="p") == "v"
    with pytest.raises(TypeError, match=r"^p\.bad must be a string, got 'int'$"):
        _ = mapping_get_str(mapping, "bad", path="p")
