import inspect
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple

from ..errors import ScalimConversionError


class ScalimCallablePreflightError(ScalimConversionError):
    """编译期 `callable` 预检查失败.

    约束:
    - 仅用于解析器已就绪边界的 `fail-fast` 校验;
    - 不得在此阶段执行用户函数体;
    - 诊断文本需尽量稳定,便于 `notebook` / 集成测试断言关键 `token`.
    """


_SignatureBindArgs = Tuple[object, ...]
_SignatureBindKwargs = Dict[str, object]
_SignatureBindCandidate = Tuple[str, _SignatureBindArgs, _SignatureBindKwargs]

_MAX_CANDIDATE_DISPLAY_LEN = 400


def try_get_signature(fn: Callable[..., Any]) -> Optional[inspect.Signature]:
    try:
        return inspect.signature(fn)
    except (TypeError, ValueError):
        return None


def _format_candidate_display(candidates: Sequence[_SignatureBindCandidate]) -> str:
    if not candidates:
        return ""
    displays = [str(display) for display, _args, _kwargs in candidates]
    # 保持顺序稳定,并避免过长.
    joined = " | ".join(displays)
    return joined[:_MAX_CANDIDATE_DISPLAY_LEN] if len(joined) > _MAX_CANDIDATE_DISPLAY_LEN else joined


def _try_bind_signature(sig: inspect.Signature, args: _SignatureBindArgs, kwargs: _SignatureBindKwargs) -> Optional[TypeError]:
    try:
        _ = sig.bind(*args, **kwargs)
    except TypeError as exc:
        return exc
    return None


def format_signature_bind_mismatch_message(
    *,
    location: str,
    reference: str,
    signature: inspect.Signature,
    bind_error: TypeError,
    candidates: Sequence[_SignatureBindCandidate],
    hint: Optional[str] = None,
    extra: Optional[str] = None,
) -> str:
    call_display = _format_candidate_display(candidates)
    msg = (
        "{location} callable preflight 失败: 函数签名不匹配 "
        "(ref={reference!r}, call=`{call_display}`, reason=`{reason}`, signature=`{signature}`)"
    ).format(
        location=str(location),
        reference=str(reference),
        call_display=str(call_display),
        reason=str(bind_error),
        signature=str(signature),
    )
    if hint:
        msg = "{}. 建议: {}".format(msg, str(hint))
    if extra:
        msg = "{} ({})".format(msg, str(extra))
    return msg


def validate_signature_accepts_any_candidate(
    *,
    location: str,
    reference: str,
    fn: Callable[..., Any],
    candidates: Sequence[_SignatureBindCandidate],
    hint: Optional[str] = None,
    extra: Optional[str] = None,
) -> None:
    """检查 `fn` 的签名是否支持任一候选调用形态.

    - 若 `inspect.signature` 不可用,直接跳过绑定校验.
    - 仅做 `Signature.bind`,不执行用户函数体.
    """

    sig = try_get_signature(fn)
    if sig is None:
        return

    last_exc: Optional[TypeError] = None
    for _display, args, kwargs in candidates:
        bind_exc = _try_bind_signature(sig, args=args, kwargs=kwargs)
        if bind_exc is None:
            return
        last_exc = bind_exc

    if last_exc is None:
        msg = "callable preflight internal error: candidates missing"
        raise ScalimCallablePreflightError(msg)

    msg = format_signature_bind_mismatch_message(
        location=location,
        reference=reference,
        signature=sig,
        bind_error=last_exc,
        candidates=candidates,
        hint=hint,
        extra=extra,
    )
    raise ScalimCallablePreflightError(msg) from last_exc


def validate_signature_binds_kwargs_keys(
    *,
    location: str,
    reference: str,
    fn: Callable[..., Any],
    kwargs_keys: Iterable[str],
    hint: Optional[str] = None,
    extra: Optional[str] = None,
) -> None:
    """仅基于 `kwargs` 键做可推理的签名绑定预检查.

    用途:
    - 加载器 `params`: 仅校验顶层 `kwargs` 键 (不渲染模板)
    """

    keys = sorted({str(k) for k in kwargs_keys if str(k)})
    if not keys:
        return

    placeholder = object()
    kwargs = dict.fromkeys(keys, placeholder)
    candidates: Tuple[_SignatureBindCandidate, ...] = (("**{" + ", ".join(keys) + "}", (), kwargs),)
    validate_signature_accepts_any_candidate(
        location=location,
        reference=reference,
        fn=fn,
        candidates=candidates,
        hint=hint,
        extra=extra,
    )


__all__ = ()
