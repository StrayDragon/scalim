import pytest

from scalim.execution.key_normalization import (
    is_experimental_key_normalization,
    normalize_key_normalization,
    should_apply_str_key_normalization,
)


def test_normalize_key_normalization_accepts_none_and_strips() -> None:
    assert normalize_key_normalization(None) == "raw"
    assert normalize_key_normalization(" auto_str ") == "auto_str"
    assert normalize_key_normalization("force_str") == "force_str"


def test_normalize_key_normalization_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Invalid key_normalization"):
        _ = normalize_key_normalization("nope")


def test_should_apply_str_key_normalization_rules() -> None:
    assert should_apply_str_key_normalization("raw", has_explicit_cast=False) is False
    assert should_apply_str_key_normalization("auto_str", has_explicit_cast=False) is True
    assert should_apply_str_key_normalization("auto_str", has_explicit_cast=True) is False
    assert should_apply_str_key_normalization("force_str", has_explicit_cast=False) is True
    assert should_apply_str_key_normalization("force_str", has_explicit_cast=True) is True


def test_is_experimental_key_normalization_variants() -> None:
    assert is_experimental_key_normalization("raw") is False
    assert is_experimental_key_normalization("auto_str") is True
    assert is_experimental_key_normalization("force_str") is True
    assert is_experimental_key_normalization("nope") is False
