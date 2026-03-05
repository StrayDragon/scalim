from collections.abc import Mapping
from typing import Any, Iterable, cast

from ....typedefs import FieldValue


def extract_field(data: Any, field_key: str) -> FieldValue:
    if isinstance(data, Mapping):
        # 注意:在 `basedpyright` 中,`isinstance(data, Mapping)` 会把类型收窄为 `Mapping[Unknown, Unknown]`,
        # 从而使 `get()` 的返回值变成“部分未知”.这里我们有意将映射的键按字符串处理.
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
