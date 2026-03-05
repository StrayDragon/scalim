from typing import Any, Dict, Hashable, Sequence

from ...guardrails import build_compute_error_guardrail_payload, fail_guardrail, record_guardrail


def handle_compute_error(
    runtime: Any,
    context: Any,
    *,
    field_key: str,
    row_id: Hashable,
    dependencies: Dict[str, Any],
    dependency_names: Sequence[str],
    exc: Exception,
    compute_mode: str,
    unexpected: bool,
) -> None:
    context.set_field_value(field_key, row_id, None)

    guardrails = runtime.guardrails
    if not guardrails.enabled:
        payload: Dict[str, Any] = {
            "field_key": field_key,
            "row_id": row_id,
            "dependencies": dependencies,
        }
        if unexpected:
            payload["unexpected"] = True
        runtime.instrumentation.emit_error(exc, payload)
        return

    if compute_mode == "quiet":
        record_guardrail(
            runtime,
            code="compute_error",
            message="Compute failed",
            action_mode="quiet",
            context=build_compute_error_guardrail_payload(
                runtime,
                field_key=field_key,
                row_id=row_id,
                dependencies=dependency_names,
                exc=exc,
                include_error=True,
                unexpected=unexpected,
            ),
        )
        return

    fail_guardrail(
        runtime,
        code="compute_error",
        message="Compute failed",
        context=build_compute_error_guardrail_payload(
            runtime,
            field_key=field_key,
            row_id=row_id,
            dependencies=dependency_names,
            exc=exc,
            unexpected=unexpected,
        ),
        action_mode="fast_fail",
        cause=exc,
    )


__all__ = [
    "handle_compute_error",
]
