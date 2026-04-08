import inspect
from typing import Any, Callable, List, Optional, Sequence, Set

from ..._internal.config_parsing.call_by import CallByValue, ParsedCallBy


def validate_call_by_signature(*, location: str, call_by: str, parsed: ParsedCallBy, fn: Callable[..., Any]) -> None:
    """校验解析后的 `call_by` 参数是否能绑定到目标函数 `fn` 的签名。

    这是一个编译期检查: 用于尽早发现"参数绑定"类错误(例如: 把位置参数传给仅关键字参数),
    避免在运行期 `guardrails` 将 `TypeError` 归为可预期的计算错误后被静默吞掉.

    说明:
    - 若 `inspect.signature` 无法获取 `fn` 的签名(少数内置/扩展可调用对象),则跳过校验以保持兼容.
    """

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return

    placeholder = object()
    args = [placeholder for _ in (parsed.args or ())]
    kwargs = {str(k): placeholder for k, _v in (parsed.kwargs or ())}

    try:
        sig.bind(*args, **kwargs)
    except TypeError as exc:
        hint = _build_keyword_only_hint(parsed=parsed, sig=sig)
        msg = "{} 的 `call_by` 参数与引用 {!r} 的函数签名不匹配: `{}` (签名: `{}`)".format(location, parsed.reference, str(exc), str(sig))
        if hint:
            msg = "{}. 建议: {}".format(msg, hint)
        msg = "{} (`call_by`={!r})".format(msg, str(call_by))
        raise TypeError(msg) from exc


def _build_keyword_only_hint(*, parsed: ParsedCallBy, sig: inspect.Signature) -> Optional[str]:
    if not parsed.args:
        return None

    if _signature_accepts_positional(sig):
        return None

    kwonly_names = _kwonly_param_names(sig)
    if not kwonly_names:
        return None

    generic = "请使用关键字传参来匹配仅关键字参数(函数签名包含 `*`)"
    if parsed.kwargs:
        return generic

    field_names = _kwonly_field_names(args=parsed.args, kwonly_names=kwonly_names)
    if not field_names:
        return generic

    rendered = ", ".join("{}={}".format(name, name) for name in field_names)
    return "可改写为: {}({})".format(parsed.reference, rendered)


def _is_field_value(value: CallByValue) -> bool:
    return str(value.kind) == "field"


def _signature_accepts_positional(sig: inspect.Signature) -> bool:
    params = list(sig.parameters.values())

    positional_only = getattr(inspect.Parameter, "POSITIONAL_ONLY", None)

    positional_kinds = [inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.VAR_POSITIONAL]
    if positional_only is not None:
        positional_kinds.append(positional_only)

    return any(p.kind in tuple(positional_kinds) for p in params)


def _kwonly_param_names(sig: inspect.Signature) -> Set[str]:
    return {p.name for p in sig.parameters.values() if p.kind == inspect.Parameter.KEYWORD_ONLY}


def _kwonly_field_names(*, args: Sequence[CallByValue], kwonly_names: Set[str]) -> Optional[List[str]]:
    field_names: List[str] = []
    for arg in args:
        if not _is_field_value(arg):
            return None
        name = str(arg.value)
        if name not in kwonly_names:
            return None
        field_names.append(name)
    return field_names or None


__all__ = ("validate_call_by_signature",)
