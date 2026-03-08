import re
from typing import Callable, ClassVar, Dict, List, Optional, Sequence, cast

from .....spec.ir.aliases import LookupKeyCast
from .....typedefs import FieldValue, LookupKey
from .....utils.converters import NamedLookupCast, auto_normalize_key, auto_str_normalize, must_to_int, must_to_str
from ...schema_dsl.models import LookupCastConfig
from ..errors import ConversionError

_SOURCE_ID_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
CALL_BY_CTX_KEY = "$ctx"


def cast_int(value: object) -> int:
    try:
        return int(value)  # pyright: ignore[reportArgumentType]
    except ValueError:
        raise
    except TypeError as exc:
        msg = "Unsupported int cast value type: {}".format(type(value).__name__)
        raise TypeError(msg) from exc


def cast_str(value: object) -> str:
    return str(value)


VALUE_CASTS: Dict[str, Callable[[FieldValue], FieldValue]] = {
    "int": cast_int,
    "str": cast_str,
    "auto": auto_str_normalize,
}


class LookupCastRegistry:
    _BASE_CASTS: ClassVar[Dict[str, LookupKeyCast]] = {
        "auto": auto_normalize_key,
        "int": must_to_int,
        "str": must_to_str,
    }

    def build(self, lookup_cast: LookupCastConfig, *, is_multi: bool) -> LookupKeyCast:
        base = self._get_base_cast(lookup_cast)
        if not is_multi:
            return NamedLookupCast(lookup_cast.name, base)
        return NamedLookupCast(lookup_cast.name, self._wrap_multi(base))

    def _get_base_cast(self, lookup_cast: LookupCastConfig) -> LookupKeyCast:
        if lookup_cast.name == "sep_first":
            return self._build_sep_first(lookup_cast.sep)
        base = self._BASE_CASTS.get(lookup_cast.name)
        if base is None:
            msg = "Unknown lookup_cast: '{}'".format(lookup_cast.name)
            raise ConversionError(msg)
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
            if not isinstance(value, (list, tuple)):
                return None
            casted: List[LookupKey] = []
            items = cast("Sequence[object]", value)
            for item in items:
                converted = base(item)
                if converted is None:
                    return None
                casted.append(converted)
            return tuple(casted)

        return _cast_multi


def validate_source_id(source_id: str, context: str) -> None:
    if not _SOURCE_ID_PATTERN.match(source_id):
        msg = "{}: source_id '{}' must match pattern [a-zA-Z_][a-zA-Z0-9_]*".format(context, source_id)
        raise ConversionError(msg)
