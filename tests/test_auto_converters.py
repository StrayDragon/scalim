from datetime import date, datetime, time
from decimal import Decimal

import pytest

from scalim.utils.converters import _format_decimal_no_exponent, auto_normalize_key, auto_str_normalize


class TestAutoStrNormalize:
    def test_none_returns_none(self) -> None:
        assert auto_str_normalize(None) is None

    def test_empty_string_passthrough(self) -> None:
        assert auto_str_normalize("") == ""

    def test_whitespace_string_passthrough(self) -> None:
        assert auto_str_normalize("   ") == "   "

    def test_int_to_string(self) -> None:
        assert auto_str_normalize(123) == "123"
        assert auto_str_normalize(-456) == "-456"
        assert auto_str_normalize(0) == "0"

    def test_float_to_string(self) -> None:
        assert auto_str_normalize(3.14) == "3.14"
        assert auto_str_normalize(2.0) == "2"
        assert auto_str_normalize(-1.5) == "-1.5"

    def test_float_nan_returns_none(self) -> None:
        assert auto_str_normalize(float("nan")) is None

    def test_float_inf_returns_none(self) -> None:
        assert auto_str_normalize(float("inf")) is None
        assert auto_str_normalize(float("-inf")) is None

    def test_decimal_to_string(self) -> None:
        assert auto_str_normalize(Decimal("123.45")) == "123.45"
        assert auto_str_normalize(Decimal("100.00")) == "100"
        assert auto_str_normalize(Decimal("-50.5")) == "-50.5"

    def test_decimal_nan_returns_none(self) -> None:
        assert auto_str_normalize(Decimal("NaN")) is None

    def test_decimal_inf_returns_none(self) -> None:
        assert auto_str_normalize(Decimal("Inf")) is None
        assert auto_str_normalize(Decimal("-Inf")) is None

    def test_string_passthrough(self) -> None:
        assert auto_str_normalize("hello") == "hello"
        assert auto_str_normalize("123") == "123"

    def test_bool_to_string(self) -> None:
        assert auto_str_normalize(True) == "1"
        assert auto_str_normalize(False) == "0"

    def test_datetime_to_iso(self) -> None:
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = auto_str_normalize(dt)
        assert result is not None
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_date_to_iso(self) -> None:
        d = date(2024, 1, 15)
        assert auto_str_normalize(d) == "2024-01-15"

    def test_time_to_iso(self) -> None:
        t = time(10, 30, 0)
        assert auto_str_normalize(t) == "10:30:00"

    def test_bytes_to_string(self) -> None:
        assert auto_str_normalize(b"hello") == "hello"
        assert auto_str_normalize(b"test123") == "test123"

    def test_bytes_decode_error_returns_none(self) -> None:
        invalid_bytes = bytes([0xFF, 0xFE])
        assert auto_str_normalize(invalid_bytes) is None

    def test_list_returns_none(self) -> None:
        assert auto_str_normalize([1, 2, 3]) is None

    def test_dict_returns_none(self) -> None:
        assert auto_str_normalize({"a": 1}) is None


class TestAutoNormalizeKey:
    def test_none_returns_none(self) -> None:
        assert auto_normalize_key(None) is None

    def test_int_passthrough(self) -> None:
        assert auto_normalize_key(123) == 123
        assert auto_normalize_key(-456) == -456

    def test_str_passthrough(self) -> None:
        assert auto_normalize_key("hello") == "hello"
        assert auto_normalize_key("123") == "123"

    def test_empty_string_passthrough(self) -> None:
        assert auto_normalize_key("") == ""

    def test_whitespace_string_passthrough(self) -> None:
        assert auto_normalize_key("   ") == "   "

    def test_float_returns_none(self) -> None:
        assert auto_normalize_key(3.14) is None

    def test_float_whole_number_returns_none(self) -> None:
        assert auto_normalize_key(5.0) is None

    def test_float_nan_returns_none(self) -> None:
        assert auto_normalize_key(float("nan")) is None

    def test_float_inf_returns_none(self) -> None:
        assert auto_normalize_key(float("inf")) is None

    def test_decimal_to_string(self) -> None:
        result = auto_normalize_key(Decimal("123.45"))
        assert result == "123.45"

    def test_decimal_whole_number_to_int(self) -> None:
        result = auto_normalize_key(Decimal("100"))
        assert result == 100
        assert isinstance(result, int)

    def test_datetime_to_string(self) -> None:
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = auto_normalize_key(dt)
        assert result is not None
        assert isinstance(result, str)

    def test_bool_to_int(self) -> None:
        result_true = auto_normalize_key(True)
        result_false = auto_normalize_key(False)
        assert result_true == 1
        assert result_false == 0
        assert type(result_true) is int
        assert type(result_false) is int

    def test_list_returns_none(self) -> None:
        assert auto_normalize_key([1, 2, 3]) is None

    def test_dict_returns_none(self) -> None:
        assert auto_normalize_key({"a": 1}) is None


class TestDecimalFormatting:
    def test_decimal_with_positive_exponent(self) -> None:
        result = auto_str_normalize(Decimal("100"))
        assert result == "100"

    def test_decimal_with_negative_exponent(self) -> None:
        result = auto_str_normalize(Decimal("0.0123"))
        assert result == "0.0123"

    def test_decimal_with_leading_zeros(self) -> None:
        result = auto_str_normalize(Decimal("0.001"))
        assert result == "0.001"

    def test_decimal_negative(self) -> None:
        result = auto_str_normalize(Decimal("-100"))
        assert result == "-100"

    def test_decimal_trailing_zeros_removed(self) -> None:
        result = auto_str_normalize(Decimal("100.00"))
        assert result == "100"


class TestAutoNormalizeKeyDecimal:
    def test_decimal_whole_number_large(self) -> None:
        result = auto_normalize_key(Decimal("1000000"))
        assert result == 1000000
        assert isinstance(result, int)

    def test_decimal_fractional(self) -> None:
        result = auto_normalize_key(Decimal("123.456"))
        assert result == "123.456"

    def test_decimal_nan(self) -> None:
        result = auto_normalize_key(Decimal("NaN"))
        assert result is None

    def test_decimal_inf(self) -> None:
        result = auto_normalize_key(Decimal("Inf"))
        assert result is None

    def test_decimal_int_conversion_value_error_falls_back(self) -> None:
        class BadDecimal(Decimal):
            def __new__(cls, value):  # type: ignore[no-untyped-def]
                return super(BadDecimal, cls).__new__(cls, value)

            def __int__(self):  # type: ignore[no-untyped-def]
                raise ValueError("bad")

        value = BadDecimal("1.23")
        result = auto_normalize_key(value)
        assert result == "1.23"


class TestIdempotency:
    def test_auto_str_normalize_idempotent(self) -> None:
        values = [123, 3.14, "hello", Decimal("100.5")]
        for val in values:
            first = auto_str_normalize(val)
            if first is not None:
                second = auto_str_normalize(first)
                assert first == second

    def test_auto_normalize_key_idempotent(self) -> None:
        values = [123, "hello", 3.14]
        for val in values:
            first = auto_normalize_key(val)
            if first is not None:
                second = auto_normalize_key(first)
                assert first == second


class TestDecimalInternalFormatting:
    def test_format_decimal_nan_uses_str(self) -> None:
        assert _format_decimal_no_exponent(Decimal("NaN")) == "NaN"
