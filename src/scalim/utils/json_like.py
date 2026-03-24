import math
from typing import Callable, Dict, Sequence, cast


def ensure_json_like(
    value: object,
    *,
    path: str,
    value_name: str,
    allowed_types_desc: str,
    dict_key_desc: str,
    require_nonempty_dict_key: bool,
    error_cls: Callable[..., Exception],
) -> object:
    """校验并归一化 `JSON-like` 值.

    - `list`/`tuple` 会归一化为 `list`.
    - `dict` 的 `key` 会归一化为 `str`(并可要求非空).
    - `float` 必须为有限值(拒绝 `NaN/Inf`).
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = "{} must be JSON-like (float must be finite)".format(str(value_name))
            raise error_cls(msg, path=str(path))
        return value
    if isinstance(value, (list, tuple)):
        items = cast("Sequence[object]", value)
        return [
            ensure_json_like(
                item,
                path=str(path),
                value_name=value_name,
                allowed_types_desc=allowed_types_desc,
                dict_key_desc=dict_key_desc,
                require_nonempty_dict_key=require_nonempty_dict_key,
                error_cls=error_cls,
            )
            for item in items
        ]
    if isinstance(value, dict):
        mapping = cast("Dict[object, object]", value)
        out: Dict[str, object] = {}
        for raw_key, raw_value in mapping.items():
            ok_key = isinstance(raw_key, str)
            if ok_key and require_nonempty_dict_key:
                ok_key = bool(str(raw_key).strip())
            if not ok_key:
                msg = "{} must be JSON-like (dict key must be {})".format(str(value_name), str(dict_key_desc))
                raise error_cls(msg, path=str(path))
            out[str(raw_key)] = ensure_json_like(
                raw_value,
                path=str(path),
                value_name=value_name,
                allowed_types_desc=allowed_types_desc,
                dict_key_desc=dict_key_desc,
                require_nonempty_dict_key=require_nonempty_dict_key,
                error_cls=error_cls,
            )
        return out
    msg = "{} must be JSON-like ({}), got {}".format(str(value_name), str(allowed_types_desc), type(value).__name__)
    raise error_cls(msg, path=str(path))
