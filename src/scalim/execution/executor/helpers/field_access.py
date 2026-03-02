from collections.abc import Iterable, Mapping
from typing import Any, cast

from ....typedefs import FieldValue


def extract_field(data: Any, field_key: str) -> FieldValue:
    if isinstance(data, Mapping):
        # NOTE: `isinstance(data, Mapping)` 在 `basedpyright` 中会收窄为 `Mapping[Unknown, Unknown]`,
        # 从而导致 `get()` 的类型变为部分未知.这里我们刻意把映射键视为字符串.
        mapping = cast("Mapping[str, Any]", data)
        return cast("FieldValue", mapping.get(field_key))

    try:
        return cast("FieldValue", object.__getattribute__(data, field_key))  # type: ignore[call-arg]
    except AttributeError:
        pass

    try:
        return cast("FieldValue", data[field_key])
    except (LookupError, TypeError):
        return None


def contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, (list, tuple)):
        for item in cast("Iterable[Any]", value):
            if isinstance(item, float):
                return True
    return False
