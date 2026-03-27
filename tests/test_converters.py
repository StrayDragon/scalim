from decimal import Decimal

import pytest

from scalim.dsl.by_yaml.runtime._internal.conversion_lookup import cast_int
from scalim.typedefs import SourceSpecIrCacheMode
from scalim._internal.utils.converters import (
    get_seps_values_first_int,
    must_get_seps_values_first_int,
    must_to_int,
    must_to_int_tuple,
    must_to_str,
    to_int,
    to_int_tuple,
    to_str,
)


def test_basic_converters() -> None:
    assert to_int("3") == 3
    assert to_int(3.2) == 3
    assert to_str(1.5) == "1.5"
    assert to_int_tuple([1, "2", 3]) == (1, 2, 3)


def test_csv_first_int() -> None:
    assert get_seps_values_first_int("10,20") == 10
    assert get_seps_values_first_int(12.7) == 12
    assert must_get_seps_values_first_int("10,20") == 10
    assert must_get_seps_values_first_int("") is None
    assert must_get_seps_values_first_int(None) is None

    with pytest.raises(ValueError):
        _ = get_seps_values_first_int("")

    with pytest.raises(TypeError):
        _ = get_seps_values_first_int(object())  # type: ignore[arg-type]


def test_must_converters() -> None:
    assert must_to_int(None) is None
    assert must_to_int("x") is None
    assert must_to_int(object()) is None
    assert must_to_int(Decimal("12")) == 12
    assert must_to_str(None) is None
    assert must_to_int_tuple(["1", 2]) == (1, 2)
    assert must_to_int_tuple([Decimal("1"), 2]) == (1, 2)
    assert must_to_int_tuple("not-a-seq") is None


def test_cache_mode_is_caching() -> None:
    assert SourceSpecIrCacheMode.NONE.is_caching() is False
    assert SourceSpecIrCacheMode.PRELOAD_FOREVER.is_caching() is True


def test_converter_edge_cases() -> None:
    assert must_to_str(123) == "123"
    assert must_to_int_tuple(None) is None
    assert must_to_int_tuple("not-a-seq") is None
    assert must_to_int_tuple(["1", "x"]) is None
    assert must_get_seps_values_first_int(3.5) == 3
    assert must_get_seps_values_first_int("bad") is None
    assert must_get_seps_values_first_int(object()) is None  # type: ignore[arg-type]


def test_cast_int_rejects_unsupported_object_type() -> None:
    assert cast_int(Decimal("12")) == 12

    with pytest.raises(ValueError):
        _ = cast_int("x")

    with pytest.raises(TypeError, match="Unsupported int cast value type"):
        _ = cast_int(object())


def test_must_to_int_falls_back_to_int_dunder() -> None:
    class SupportsIntLike:
        def __int__(self) -> int:
            return 7

    assert must_to_int(SupportsIntLike()) == 7
