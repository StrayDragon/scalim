import math
import re
from decimal import Decimal, InvalidOperation
from typing import Callable, ClassVar, Dict, List, Optional, Sequence

from ....._internal.utils.converters import NamedLookupCast, auto_normalize_key, auto_str_normalize, must_to_int, must_to_str
from .....spec.ir.aliases import LookupKeyCast
from .....typedefs import FieldValue, LookupKey
from .....vendor.compact.typing_extensionsx import TypeGuard
from ...schema_dsl.models import LookupCastConfig
from ..errors import ScalimConversionError

_SOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
CALL_BY_CTX_KEY = "$ctx"


def _is_sequence(value: object) -> TypeGuard[Sequence[object]]:
    return isinstance(value, (list, tuple))


def cast_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)  # pyright: ignore[reportArgumentType]
    except ValueError:
        raise
    except TypeError as exc:
        msg = "Unsupported int cast value type: {}".format(type(value).__name__)
        raise TypeError(msg) from exc


def cast_str(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _cast_decimal_from_float(value: float) -> Decimal:
    if not math.isfinite(value):
        msg = "Invalid decimal float literal: {!r}".format(value)
        raise ValueError(msg)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        msg = "Invalid decimal float literal: {!r}".format(value)
        raise ValueError(msg) from exc


def _cast_decimal_from_string(value: str) -> Optional[Decimal]:
    text = value.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        msg = "Invalid decimal string literal: {!r}".format(value)
        raise ValueError(msg) from exc


def cast_decimal(value: object) -> Optional[Decimal]:
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
    msg = "Unsupported decimal cast value type: {}".format(type(value).__name__)
    raise TypeError(msg)


VALUE_CASTS: Dict[str, Callable[[FieldValue], FieldValue]] = {
    "int": cast_int,
    "str": cast_str,
    "auto": auto_str_normalize,
    "decimal": cast_decimal,
}


class LookupCastRegistry:
    _BASE_CASTS: ClassVar[Dict[str, LookupKeyCast]] = {
        "auto": auto_normalize_key,
        "int": must_to_int,
        "str": must_to_str,
    }

    def build(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> LookupKeyCast:
        base = self._get_base_cast(lookup_cast)
        meta: Dict[str, object] = {}
        if lookup_cast.name == "sep_first":
            meta["sep"] = lookup_cast.sep or ","
        if not is_multi:
            return NamedLookupCast(lookup_cast.name, base, meta=meta)
        return NamedLookupCast(lookup_cast.name, self._wrap_multi(base), meta=meta)

    def _get_base_cast(self, lookup_cast: LookupCastConfig) -> LookupKeyCast:
        if lookup_cast.name == "sep_first":
            return self._build_sep_first(lookup_cast.sep)
        base = self._BASE_CASTS.get(lookup_cast.name)
        if base is None:
            msg = "Unknown lookup_cast: '{}'".format(lookup_cast.name)
            raise ScalimConversionError(msg)
        return base

    def _build_sep_first(self, sep: Optional[str]) -> LookupKeyCast:
        separator = sep or ","

        def _cast(value: object) -> Optional[LookupKey]:
            if value is None:
                return None
            raw = str(value)
            first = raw.split(separator, maxsplit=1)[0].strip()
            if not first:
                return None
            return auto_normalize_key(first)

        return _cast

    def _wrap_multi(self, base: LookupKeyCast) -> LookupKeyCast:
        def _cast_multi(value: object) -> Optional[LookupKey]:
            if not _is_sequence(value):
                return None
            casted: List[LookupKey] = []
            for item in value:
                converted = base(item)
                if converted is None:
                    return None
                casted.append(converted)
            return tuple(casted)

        return _cast_multi


def validate_source_id(source_id: str, context: str) -> None:
    if not _SOURCE_ID_PATTERN.match(source_id):
        msg = "{}: source_id '{}' must match pattern [a-zA-Z_][a-zA-Z0-9_]*".format(context, source_id)
        raise ScalimConversionError(msg)


__all__ = []
