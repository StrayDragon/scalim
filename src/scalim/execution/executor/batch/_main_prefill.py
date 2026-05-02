from typing import Callable, Dict, Hashable, List, Mapping, Optional, Set, Tuple, Union

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


def _build_main_field_ops(
    *,
    main_field_specs: List[Tuple[str, FieldIr]],
    get_value_transform: Callable[[str], Optional[Callable[[FieldValue], FieldValue]]],
) -> List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]]:
    # 热路径: 预计算每个字段的提取方式/`value_transform`,避免逐行重复查找.
    #
    # 注意:
    # - `value_transform` 以 `field_id` 为索引,在整个 `pipeline` 中是稳定的,可以安全提到循环外.
    # - `data_key` 仅用于 `guardrails` 的诊断信息,提到循环外不会改变语义.
    ops: List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]] = []
    for field_key, field_spec in main_field_specs:
        data_key = field_spec.extract_expr or field_spec.data_key or field_key
        ops.append((field_key, data_key, field_spec.extract_segments, get_value_transform(field_spec.field_id)))
    return ops


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

    get_value_transform = runtime.runtime_bindings.get_value_transform
    context_set_field_value = context.set_field_value
    extract_field_value_segments = extract_field_segments
    extract_field_value = extract_field
    enforce_required = maybe_enforce_required_field_value
    handle_transform_error = handle_loader_transform_error

    main_field_ops = _build_main_field_ops(main_field_specs=main_field_specs, get_value_transform=get_value_transform)

    for row_id, row_data in main_rows.items():
        for field_key, data_key, segments, value_transform in main_field_ops:
            field_value: FieldValue = extract_field_value_segments(row_data, segments)
            try:
                if value_transform is not None:
                    field_value = value_transform(field_value)
            except Exception as exc:
                if not guardrails.enabled:
                    raise
                handle_transform_error(
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
            context_set_field_value(field_key, row_id, field_value)
            enforce_required(
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
            field_value = extract_field_value(row_data, field_key)
            context_set_field_value(field_key, row_id, field_value)
            enforce_required(
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
