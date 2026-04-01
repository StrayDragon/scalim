from typing import Dict, Hashable, List, Mapping, Optional, Set, Tuple

from ....spec.ir import FieldIr
from ....typedefs import FieldValue, RowData
from ...context import BatchContext
from ..helpers.field_access import extract_field, extract_field_segments
from ..operators._internal.loader_guardrails import handle_loader_transform_error, maybe_enforce_required_field_value
from ..runtime.runtime import ExecutionRuntime


def collect_main_source_fields(
    *,
    plan_field_specs: Mapping[str, object],
    field_keys: Set[str],
    main_source_id: str,
) -> Tuple[List[Tuple[str, FieldIr]], List[str]]:
    main_field_specs: List[Tuple[str, FieldIr]] = []
    passthrough_fields: List[str] = []

    for field_key in field_keys:
        field_spec = plan_field_specs.get(field_key)
        if field_spec is None:
            passthrough_fields.append(field_key)
            continue
        if isinstance(field_spec, FieldIr) and field_spec.source.source_id == main_source_id:
            main_field_specs.append((field_key, field_spec))

    return main_field_specs, passthrough_fields


def prefill_main_source_fields(
    *,
    context: BatchContext,
    plan_field_specs: Mapping[str, object],
    runtime: ExecutionRuntime,
    main_rows: Optional[Dict[Hashable, RowData]],
    required_fields: Optional[Set[str]],
) -> None:
    if main_rows is None or runtime.main_source is None:
        return

    field_keys = required_fields or set(plan_field_specs.keys())
    main_source_id = runtime.main_source.source_id

    main_field_specs, passthrough_fields = collect_main_source_fields(
        plan_field_specs=plan_field_specs,
        field_keys=set(field_keys),
        main_source_id=main_source_id,
    )

    if not main_field_specs and not passthrough_fields:
        return

    guardrails = runtime.guardrails
    required_guardrail_keys: Set[str] = set()
    if guardrails.enabled and guardrails.loader.required_fields:
        required_guardrail_keys = set(field_keys) & set(guardrails.loader.required_fields)
    required_mode = guardrails.mode
    transform_mode = guardrails.effective_loader_transform_mode()

    for row_id, row_data in main_rows.items():
        for field_key, field_spec in main_field_specs:
            data_key = field_spec.extract_expr or field_spec.data_key or field_key
            field_value: FieldValue = extract_field_segments(row_data, field_spec.extract_segments)
            try:
                field_value = field_spec.apply_transform(field_value)
            except Exception as exc:
                if not guardrails.enabled:
                    raise
                handle_loader_transform_error(
                    runtime,
                    source_id=main_source_id,
                    row_id=row_id,
                    field_key=field_key,
                    data_key=data_key,
                    exc=exc,
                    mode=transform_mode,
                    main_source=True,
                )
                field_value = None
            context.set_field_value(field_key, row_id, field_value)
            maybe_enforce_required_field_value(
                runtime,
                source_id=main_source_id,
                row_id=row_id,
                field_key=field_key,
                value=field_value,
                required_field_keys=required_guardrail_keys,
                mode=required_mode,
                reason="value is None",
                main_source=True,
            )
        for field_key in passthrough_fields:
            field_value = extract_field(row_data, field_key)
            context.set_field_value(field_key, row_id, field_value)
            maybe_enforce_required_field_value(
                runtime,
                source_id=main_source_id,
                row_id=row_id,
                field_key=field_key,
                value=field_value,
                required_field_keys=required_guardrail_keys,
                mode=required_mode,
                reason="value is None",
                main_source=True,
            )


__all__ = ()
