from collections.abc import Hashable
from typing import Any

from .....typedefs import FieldValue
from ...guardrails import build_guardrail_once_key, build_loader_row_guardrail_payload, fail_guardrail, record_guardrail
from ...runtime.runtime import ExecutionRuntime
from .sentinels import MISSING


def record_or_fail_required_field_missing(
    runtime: ExecutionRuntime,
    *,
    source_id: str,
    row_id: Hashable,
    field_key: str,
    reason: str,
    mode: str,
    is_ref_loader: bool = False,
    main_source: bool = False,
    lookup_key: Any = MISSING,
) -> None:
    payload = build_loader_row_guardrail_payload(
        runtime,
        source_id=source_id,
        row_id=row_id,
        field_key=field_key,
        reason=reason,
        is_ref_loader=is_ref_loader,
        lookup_key=lookup_key,
        include_lookup_key=lookup_key is not MISSING,
        main_source=main_source,
    )

    if mode == "quiet":
        record_guardrail(
            runtime,
            code="loader_required_field_missing",
            message="Required field is missing or None",
            action_mode="quiet",
            context=payload,
            once_key=build_guardrail_once_key("loader_required_field_missing", source_id, field_key),
        )
        return

    fail_guardrail(
        runtime,
        code="loader_required_field_missing",
        message="Required field is missing or None",
        context=payload,
        action_mode="fast_fail",
    )


def maybe_enforce_required_field_value(
    runtime: ExecutionRuntime,
    *,
    source_id: str,
    row_id: Hashable,
    field_key: str,
    value: FieldValue,
    required_field_keys: set[str],
    mode: str,
    reason: str,
    is_ref_loader: bool = False,
    main_source: bool = False,
    lookup_key: Any = MISSING,
) -> None:
    if not required_field_keys or field_key not in required_field_keys or value is not None:
        return

    record_or_fail_required_field_missing(
        runtime,
        source_id=source_id,
        row_id=row_id,
        field_key=field_key,
        reason=reason,
        mode=mode,
        is_ref_loader=is_ref_loader,
        main_source=main_source,
        lookup_key=lookup_key,
    )


def handle_loader_extractor_error(
    runtime: ExecutionRuntime,
    *,
    source_id: str,
    row_id: Hashable,
    exc: Exception,
    mode: str,
    is_ref_loader: bool = False,
    main_source: bool = False,
    lookup_key: Any = MISSING,
) -> None:
    if mode == "quiet":
        payload = build_loader_row_guardrail_payload(
            runtime,
            source_id=source_id,
            row_id=row_id,
            error_type=type(exc).__name__,
            error=str(exc),
            is_ref_loader=is_ref_loader,
            lookup_key=lookup_key,
            include_lookup_key=lookup_key is not MISSING,
            main_source=main_source,
        )
        record_guardrail(
            runtime,
            code="loader_extractor_error",
            message="Loader extractor failed",
            action_mode="quiet",
            context=payload,
        )
        return

    payload = build_loader_row_guardrail_payload(
        runtime,
        source_id=source_id,
        row_id=row_id,
        error_type=type(exc).__name__,
        is_ref_loader=is_ref_loader,
        lookup_key=lookup_key,
        include_lookup_key=lookup_key is not MISSING,
        main_source=main_source,
    )
    fail_guardrail(
        runtime,
        code="loader_extractor_error",
        message="Loader extractor failed",
        context=payload,
        action_mode="fast_fail",
        cause=exc,
    )


def handle_loader_transform_error(
    runtime: ExecutionRuntime,
    *,
    source_id: str,
    row_id: Hashable,
    field_key: str,
    data_key: str,
    exc: Exception,
    mode: str,
    is_ref_loader: bool = False,
    main_source: bool = False,
    lookup_key: Any = MISSING,
) -> None:
    if mode == "quiet":
        payload = build_loader_row_guardrail_payload(
            runtime,
            source_id=source_id,
            row_id=row_id,
            field_key=field_key,
            data_key=data_key,
            error_type=type(exc).__name__,
            error=str(exc),
            is_ref_loader=is_ref_loader,
            lookup_key=lookup_key,
            include_lookup_key=lookup_key is not MISSING,
            main_source=main_source,
        )
        record_guardrail(
            runtime,
            code="loader_transform_error",
            message="Loader field transform failed",
            action_mode="quiet",
            context=payload,
        )
        return

    payload = build_loader_row_guardrail_payload(
        runtime,
        source_id=source_id,
        row_id=row_id,
        field_key=field_key,
        data_key=data_key,
        error_type=type(exc).__name__,
        is_ref_loader=is_ref_loader,
        lookup_key=lookup_key,
        include_lookup_key=lookup_key is not MISSING,
        main_source=main_source,
    )
    fail_guardrail(
        runtime,
        code="loader_transform_error",
        message="Loader field transform failed",
        context=payload,
        action_mode="fast_fail",
        cause=exc,
    )


__all__ = [
    "handle_loader_extractor_error",
    "handle_loader_transform_error",
    "maybe_enforce_required_field_value",
    "record_or_fail_required_field_missing",
]
