from collections.abc import Mapping
from typing import Any, Iterable, Tuple, Union, cast

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


def extract_field_segments(data: Any, segments: Tuple[Union[str, int], ...]) -> FieldValue:
    """
    按 `segments` 逐段读取字段值.

    注意:
    - `int` 段仅表示映射键,不得索引 `list`/`tuple`
    - 每段按顺序尝试: 映射键 -> (字符串段) 属性 -> `__getitem__`
    - 任一段读取失败返回 `None`
    """
    current: Any = data
    for segment in segments:
        if current is None:
            return None
        current = _extract_field_segment(current, segment)
    return cast("FieldValue", current)


def _extract_field_segment(data: Any, segment: Union[str, int]) -> Any:
    if isinstance(data, Mapping):
        mapping = cast("Mapping[Any, Any]", data)
        if segment in mapping:
            return mapping[segment]
        return None

    if isinstance(segment, str):
        try:
            return object.__getattribute__(data, segment)  # type: ignore[call-arg]
        except AttributeError:
            pass

    if isinstance(segment, int) and isinstance(data, (list, tuple)):
        return None

    try:
        return data[segment]
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
