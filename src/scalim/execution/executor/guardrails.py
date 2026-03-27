from typing import Any, Dict, Hashable, Optional, Sequence, Tuple

from ..guardrails import GuardrailMode, ScalimGuardrailViolationError


def build_guardrail_once_key(code: str, *parts: Any) -> Tuple[str, ...]:
    return (code, *tuple(str(part) for part in parts))


def build_loader_row_guardrail_payload(
    runtime: Any,
    *,
    source_id: str,
    row_id: Hashable,
    field_key: Optional[str] = None,
    reason: Optional[str] = None,
    data_key: Optional[str] = None,
    error_type: Optional[str] = None,
    error: Optional[str] = None,
    is_ref_loader: bool = False,
    lookup_key: Any = None,
    include_lookup_key: bool = False,
    main_source: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source_id": source_id,
        "batch_num": runtime.batch_num,
        "row_id": row_id,
    }

    if field_key is not None:
        payload["field_key"] = field_key
    if reason is not None:
        payload["reason"] = reason
    if data_key is not None:
        payload["data_key"] = data_key
    if error_type is not None:
        payload["error_type"] = error_type
    if error is not None:
        payload["error"] = error
    if include_lookup_key:
        payload["lookup_key"] = lookup_key
    if is_ref_loader:
        payload["is_ref_loader"] = True
    if main_source:
        payload["main_source"] = True

    return payload


def build_loader_result_guardrail_payload(
    runtime: Any,
    *,
    source_id: str,
    result: Any,
    is_ref_loader: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "source_id": source_id,
        "batch_num": runtime.batch_num,
        "result_type": type(result).__name__,
    }
    if is_ref_loader:
        payload["is_ref_loader"] = True
    return payload


def build_compute_error_guardrail_payload(
    runtime: Any,
    *,
    field_key: str,
    row_id: Hashable,
    dependencies: Sequence[str],
    exc: Exception,
    include_error: bool = False,
    unexpected: bool = False,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "batch_num": runtime.batch_num,
        "field_key": field_key,
        "row_id": row_id,
        "dependencies": list(dependencies),
        "error_type": type(exc).__name__,
    }
    if include_error:
        payload["error"] = str(exc)
    if unexpected:
        payload["unexpected"] = True
    return payload


def build_guardrail_context(
    runtime: Any,
    *,
    code: str,
    action_mode: GuardrailMode,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    payload = dict(context)
    payload["guardrail"] = True
    payload["guardrail_code"] = code
    payload["guardrail_mode"] = action_mode
    payload["guardrail_configured_mode"] = runtime.guardrails.mode
    return payload


def record_guardrail(
    runtime: Any,
    *,
    code: str,
    message: str,
    action_mode: GuardrailMode,
    context: Dict[str, Any],
    once_key: Optional[Tuple[str, ...]] = None,
) -> None:
    payload = build_guardrail_context(runtime, code=code, action_mode=action_mode, context=context)
    if once_key is not None:
        if once_key in runtime.guardrail_logged:
            return
        runtime.guardrail_logged.add(once_key)
    runtime.instrumentation.emit_error(ScalimGuardrailViolationError(message, code=code, context=payload), payload)


def fail_guardrail(
    runtime: Any,
    *,
    code: str,
    message: str,
    context: Dict[str, Any],
    action_mode: GuardrailMode = "fast_fail",
    cause: Optional[Exception] = None,
) -> None:
    payload = build_guardrail_context(runtime, code=code, action_mode=action_mode, context=context)
    if cause is not None:
        payload["cause_type"] = type(cause).__name__
        payload["cause"] = str(cause)
    violation = ScalimGuardrailViolationError(message, code=code, context=payload)
    runtime.instrumentation.emit_error(violation, payload)
    raise violation
