from dataclasses import dataclass
from typing import Any

from .....spec.ir.relations import LookupStepIr
from ...guardrails import build_guardrail_once_key, fail_guardrail, record_guardrail


@dataclass
class _RelationGuardrailStats:
    attempts: int = 0
    null_key: int = 0
    type_error: int = 0


def _stats_for_step(runtime: Any, step: LookupStepIr) -> tuple[int, _RelationGuardrailStats]:
    step_key = id(step)
    stats = runtime.relation_guardrail_stats.get(step_key)
    if stats is None:
        stats = _RelationGuardrailStats()
        runtime.relation_guardrail_stats[step_key] = stats
    return step_key, stats


def _emit_or_raise_relation_guardrail(
    runtime: Any,
    step: LookupStepIr,
    *,
    code: str,
    message: str,
    payload: dict[str, Any],
    step_key: int,
) -> None:
    guardrails = runtime.guardrails
    action_mode = guardrails.mode
    once_key = build_guardrail_once_key(code, step.to_source.source_id, step_key)

    if action_mode == "quiet":
        record_guardrail(
            runtime,
            code=code,
            message=message,
            action_mode=action_mode,
            context=payload,
            once_key=once_key,
        )
        return

    fail_guardrail(
        runtime,
        code=code,
        message=message,
        context=payload,
        action_mode=action_mode,
    )


def maybe_enforce_relation_guardrails(
    runtime: Any,
    step: LookupStepIr,
    *,
    status: str,
    error_message: str | None,
) -> None:
    guardrails = runtime.guardrails
    if not guardrails.enabled or not guardrails.relations_enabled():
        return

    step_key, stats = _stats_for_step(runtime, step)
    stats.attempts += 1
    if status == "null_key":
        stats.null_key += 1
    elif status == "type_error":
        stats.type_error += 1

    attempts = stats.attempts or 1
    null_key_rate = stats.null_key / attempts
    type_error_rate = stats.type_error / attempts

    null_key_max_rate = guardrails.relations.null_key_max_rate
    if null_key_max_rate is not None and null_key_rate > null_key_max_rate:
        payload = {
            "source_id": step.to_source.source_id,
            "batch_num": runtime.batch_num,
            "from_fields": step.get_from_fields(),
            "to_key": step.get_to_key_or_source_key(),
            "attempts": attempts,
            "null_key": stats.null_key,
            "type_error": stats.type_error,
            "null_key_rate": null_key_rate,
            "null_key_max_rate": null_key_max_rate,
            "status": status,
            "error_message": error_message,
        }
        _emit_or_raise_relation_guardrail(
            runtime,
            step,
            code="relation_null_key_rate_exceeded",
            message="Relation null_key rate exceeded",
            payload=payload,
            step_key=step_key,
        )

    type_error_max_rate = guardrails.relations.type_error_max_rate
    if type_error_max_rate is not None and type_error_rate > type_error_max_rate:
        payload = {
            "source_id": step.to_source.source_id,
            "batch_num": runtime.batch_num,
            "from_fields": step.get_from_fields(),
            "to_key": step.get_to_key_or_source_key(),
            "attempts": attempts,
            "null_key": stats.null_key,
            "type_error": stats.type_error,
            "type_error_rate": type_error_rate,
            "type_error_max_rate": type_error_max_rate,
            "status": status,
            "error_message": error_message,
        }
        _emit_or_raise_relation_guardrail(
            runtime,
            step,
            code="relation_type_error_rate_exceeded",
            message="Relation type_error rate exceeded",
            payload=payload,
            step_key=step_key,
        )


__all__ = [
    "maybe_enforce_relation_guardrails",
]
