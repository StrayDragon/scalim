import math
import re
from collections.abc import Callable, Sequence
from decimal import Decimal, InvalidOperation
from typing import ClassVar, TypeGuard

from ....._internal.utils.converters import NamedLookupCast, auto_normalize_key, auto_str_normalize, must_to_int, must_to_str
from .....spec.ir.aliases import LookupKeyCast
from .....spec.ir.lookup_casts import LookupCastSpecIr
from .....typedefs import FieldValue, LookupKey, RuntimeValue
from ..errors import ScalimConversionError

_SOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
CALL_BY_CTX_KEY = "$ctx"


def _is_sequence(value: RuntimeValue) -> TypeGuard[Sequence[RuntimeValue]]:
    return isinstance(value, (list, tuple))


def cast_int(value: RuntimeValue) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # pyright: ignore[reportArgumentType]
    except ValueError:
        raise
    except TypeError as exc:
        msg = f"Unsupported int cast value type: {type(value).__name__}"
        raise TypeError(msg) from exc


def cast_str(value: RuntimeValue) -> str | None:
    if value is None:
        return None
    return str(value)


def _cast_decimal_from_float(value: float) -> Decimal:
    if not math.isfinite(value):
        msg = f"Invalid decimal float literal: {value!r}"
        raise ValueError(msg)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        msg = f"Invalid decimal float literal: {value!r}"
        raise ValueError(msg) from exc


def _cast_decimal_from_string(value: str) -> Decimal | None:
    text = value.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        msg = f"Invalid decimal string literal: {value!r}"
        raise ValueError(msg) from exc


def cast_decimal(value: RuntimeValue) -> Decimal | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(1) if value else Decimal(0)
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return _cast_decimal_from_float(value)
    if isinstance(value, str):
        return _cast_decimal_from_string(value)
    msg = f"Unsupported decimal cast value type: {type(value).__name__}"
    raise TypeError(msg)


VALUE_CASTS: dict[str, Callable[[FieldValue], FieldValue]] = {
    "int": cast_int,
    "str": cast_str,
    "auto": auto_str_normalize,
    "decimal": cast_decimal,
}


class LookupCastRegistry:
    _BASE_CASTS: ClassVar[dict[str, LookupKeyCast]] = {
        "auto": auto_normalize_key,
        "int": must_to_int,
        "str": must_to_str,
    }

    def build(self, lookup_cast: LookupCastSpecIr, *, is_multi: bool) -> LookupKeyCast:
        base = self._get_base_cast(lookup_cast)
        meta: dict[str, RuntimeValue] = {}
        if lookup_cast.name == "sep_first":
            meta["sep"] = lookup_cast.sep or ","
        if not is_multi:
            return NamedLookupCast(lookup_cast.name, base, meta=meta)
        return NamedLookupCast(lookup_cast.name, self._wrap_multi(base), meta=meta)

    def _get_base_cast(self, lookup_cast: LookupCastSpecIr) -> LookupKeyCast:
        if lookup_cast.name == "sep_first":
            return self._build_sep_first(lookup_cast.sep)
        base = self._BASE_CASTS.get(lookup_cast.name)
        if base is None:
            msg = f"Unknown lookup_cast: '{lookup_cast.name}'"
            raise ScalimConversionError(msg)
        return base

    def _build_sep_first(self, sep: str | None) -> LookupKeyCast:
        separator = sep or ","

        def _cast(value: RuntimeValue) -> LookupKey | None:
            if value is None:
                return None
            raw = str(value)
            first = raw.split(separator, maxsplit=1)[0].strip()
            if not first:
                return None
            return auto_normalize_key(first)

        return _cast

    def _wrap_multi(self, base: LookupKeyCast) -> LookupKeyCast:
        def _cast_multi(value: RuntimeValue) -> LookupKey | None:
            if not _is_sequence(value):
                return None
            casted: list[LookupKey] = []
            for item in value:
                converted = base(item)
                if converted is None:
                    return None
                casted.append(converted)
            return tuple(casted)

        return _cast_multi


def validate_source_id(source_id: str, context: str) -> None:
    if not _SOURCE_ID_PATTERN.match(source_id):
        msg = f"{context}: source_id '{source_id}' must match pattern [a-zA-Z_][a-zA-Z0-9_]*"
        raise ScalimConversionError(msg)


__all__ = ()
