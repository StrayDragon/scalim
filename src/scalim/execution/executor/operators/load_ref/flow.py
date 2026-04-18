from typing import TYPE_CHECKING, Dict, Hashable, List, Optional, Set, Tuple

from .....spec.ir import CallBySpecIr, ComputeCallContextIr, FieldIr, LookupStepIr
from .....spec.ir._source_contracts import LookupSourceRefIrBase
from .....typedefs import FieldValue, LoaderResultMapping, LookupKey
from ...helpers.field_access import extract_field, extract_field_segments
from .._internal.loader_guardrails import (
    handle_loader_extractor_error,
    handle_loader_transform_error,
    maybe_enforce_required_field_value,
)
from .._internal.sentinels import MISSING
from .context import LoadRefExecutionContext

if TYPE_CHECKING:
    from ...runtime.runtime import ExecutionRuntime


def _eval_ref_default_call_by(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    *,
    field_key: str,
    idx: int,
    call_by: CallBySpecIr,
) -> FieldValue:
    calculator = exec_ctx.runtime.runtime_bindings.get_ref_default_calculator(field_key, int(idx))
    if calculator is None:
        msg = "Missing runtime ref default calculator for field_id={!r}, default_idx={}".format(field_key, int(idx))
        raise KeyError(msg)

    deps = tuple(str(x) for x in (call_by.field_names or ()))
    dep_values: List[FieldValue] = []
    dep_payload: Dict[str, FieldValue] = {}
    for dep in deps:
        v: FieldValue = exec_ctx.context.get_field_value(dep, row_id)
        dep_values.append(v)
        dep_payload[str(dep)] = v

    ctx_obj = ComputeCallContextIr(
        row_id=row_id,
        batch_num=int(exec_ctx.runtime.batch_num),
        field_id=str(field_key),
        deps=deps,
        values=dep_payload,
    )

    return calculator(*dep_values, ctx=ctx_obj)


def _resolve_ref_default_value_on_relation_miss(  # noqa: PLR0911
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    *,
    field_key: str,
) -> Tuple[FieldValue, bool]:
    field_spec = exec_ctx.runtime.field_specs.get(field_key)
    if not isinstance(field_spec, FieldIr):
        return None, False

    cases = tuple(field_spec.default_cases or ())
    if not cases:
        return None, False

    for idx, case in enumerate(cases):
        when = str(case.when or "").strip()
        # 注意: `when` 枚举为扩展预留; `v1` 仅实现 `relation_miss`.
        if when != "relation_miss":
            continue

        kind = str(case.kind or "").strip()
        if kind == "literal":
            return case.literal, True
        if kind == "call_by":
            call_by = case.call_by
            if call_by is None:
                return None, True
            return _eval_ref_default_call_by(exec_ctx, row_id, field_key=field_key, idx=int(idx), call_by=call_by), True

        return None, True

    return None, False


def _write_relation_miss_field_value(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    *,
    field_key: str,
    required_field_keys: Set[str],
    required_mode: str,
    transform_mode: str,
    reason: str,
    lookup_key: object,
) -> None:
    field_spec = exec_ctx.runtime.field_specs.get(field_key)
    source_id = "(unknown)"
    data_key = "(default)"
    if isinstance(field_spec, FieldIr):
        source_id = str(field_spec.source.source_id or "")
        data_key = str(field_spec.extract_expr or field_spec.data_key or data_key)

    value, default_applied = _resolve_ref_default_value_on_relation_miss(exec_ctx, row_id, field_key=field_key)
    if default_applied:
        exec_ctx.record_default_applied(field_key)

    value_transform = exec_ctx.runtime.runtime_bindings.get_value_transform(field_key)
    try:
        value = value_transform(value) if value_transform is not None else value
    except Exception as exc:
        guardrails = exec_ctx.runtime.guardrails
        if not guardrails.enabled:
            raise
        handle_loader_transform_error(
            exec_ctx.runtime,
            source_id=source_id,
            row_id=row_id,
            field_key=field_key,
            data_key=data_key,
            exc=exc,
            mode=transform_mode,
            is_ref_loader=True,
            lookup_key=lookup_key,
        )
        value = None

    exec_ctx.context.set_field_value(field_key, row_id, value)
    maybe_enforce_required_field_value(
        exec_ctx.runtime,
        source_id=source_id,
        row_id=row_id,
        field_key=field_key,
        value=value,
        required_field_keys=required_field_keys,
        mode=required_mode,
        reason=reason,
        is_ref_loader=True,
        lookup_key=lookup_key,
    )


def _null_fill_row(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    *,
    null_fill_fields: Optional[Tuple[str, ...]],
) -> None:
    if not null_fill_fields:
        return
    guardrails = exec_ctx.runtime.guardrails
    required_mode = guardrails.mode
    transform_mode = guardrails.effective_loader_transform_mode()
    for field_key in null_fill_fields:
        _write_relation_miss_field_value(
            exec_ctx,
            row_id,
            field_key=field_key,
            required_field_keys=set(),
            required_mode=required_mode,
            transform_mode=transform_mode,
            reason="relation lookup miss (null/invalid key or step miss)",
            lookup_key=MISSING,
        )


def init_first_fk_mapping(
    exec_ctx: LoadRefExecutionContext,
    first_step: LookupStepIr,
    *,
    null_fill_fields: Optional[Tuple[str, ...]] = None,
) -> Dict[Hashable, LookupKey]:
    pk_to_first_fk: Dict[Hashable, LookupKey] = {}

    for row_id in exec_ctx.batch_row_nth:
        if first_step.is_multi_field():
            normalized_key = _collect_multi_field_fk(exec_ctx, row_id, first_step)
        else:
            from_field = first_step.get_from_fields()[0]
            single_fk_value: FieldValue = exec_ctx.context.get_field_value(from_field, row_id)
            normalized_key = exec_ctx.normalize_key(row_id, single_fk_value, first_step)

        if normalized_key is not None:
            pk_to_first_fk[row_id] = normalized_key
        else:
            _null_fill_row(exec_ctx, row_id, null_fill_fields=null_fill_fields)

    return pk_to_first_fk


def _collect_multi_field_fk(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    step: LookupStepIr,
) -> Optional[Hashable]:
    from_fields = step.get_from_fields()
    fk_values: List[FieldValue] = []
    for key in from_fields:
        val: FieldValue = exec_ctx.context.get_field_value(key, row_id)
        if val is None:
            _ = exec_ctx.normalize_key(row_id, None, step)
            return None
        fk_values.append(val)
    raw_tuple = tuple(fk_values)
    return exec_ctx.normalize_key(row_id, raw_tuple, step)


def _resolve_next_step_fk(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    data: object,
    step: LookupStepIr,
) -> Optional[LookupKey]:
    from_field = step.from_field
    if isinstance(from_field, str):
        next_fk: FieldValue = extract_field(data, from_field)
        if next_fk is None:
            _ = exec_ctx.normalize_key(row_id, None, step)
            return None
        return exec_ctx.normalize_key(row_id, next_fk, step)
    return _collect_multi_field_fk_from_data(exec_ctx, row_id, data, step)


def build_next_mapping(
    exec_ctx: LoadRefExecutionContext,
    current_mapping: Dict[Hashable, LookupKey],
    intermediate_result: LoaderResultMapping,
    next_step: LookupStepIr,
    *,
    null_fill_fields: Optional[Tuple[str, ...]] = None,
) -> Dict[Hashable, LookupKey]:
    new_mapping: Dict[Hashable, LookupKey] = {}

    for row_id, fk_value in current_mapping.items():
        if fk_value not in intermediate_result:
            _null_fill_row(exec_ctx, row_id, null_fill_fields=null_fill_fields)
            continue

        data = intermediate_result[fk_value]

        normalized_key = _resolve_next_step_fk(exec_ctx, row_id, data, next_step)
        if normalized_key is not None:
            new_mapping[row_id] = normalized_key
        else:
            _null_fill_row(exec_ctx, row_id, null_fill_fields=null_fill_fields)

    return new_mapping


def _collect_multi_field_fk_from_data(
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    data: object,
    step: LookupStepIr,
) -> Optional[LookupKey]:
    from_fields = step.get_from_fields()
    fk_values: List[FieldValue] = []
    for key in from_fields:
        val: FieldValue = extract_field(data, key)
        if val is None:
            _ = exec_ctx.normalize_key(row_id, None, step)
            return None
        fk_values.append(val)
    raw_tuple = tuple(fk_values)
    return exec_ctx.normalize_key(row_id, raw_tuple, step)


def _resolve_ref_required_field_keys(
    *,
    runtime: "ExecutionRuntime",
    group_field_keys: Tuple[str, ...],
) -> Set[str]:
    guardrails = runtime.guardrails
    if guardrails.enabled and guardrails.loader.required_fields:
        return set(group_field_keys) & set(guardrails.loader.required_fields)
    return set()


def _apply_ref_extractor(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    row_id: Hashable,
    lookup_key: LookupKey,
    intermediate_result: LoaderResultMapping,
    data: object,
    transform_mode: str,
) -> object:
    extractor = exec_ctx.runtime.runtime_bindings.get_loader_extractor(source.source_id)
    if extractor is None:
        return data
    try:
        return extractor(lookup_key, intermediate_result)
    except Exception as exc:
        guardrails = exec_ctx.runtime.guardrails
        if not guardrails.enabled:
            raise
        handle_loader_extractor_error(
            exec_ctx.runtime,
            source_id=source.source_id,
            row_id=row_id,
            exc=exc,
            mode=transform_mode,
            is_ref_loader=True,
            lookup_key=lookup_key,
        )
        return None


def _resolve_ref_field_value(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    row_id: Hashable,
    lookup_key: LookupKey,
    field_key: str,
    data: object,
    transform_mode: str,
) -> FieldValue:
    field_spec = exec_ctx.runtime.field_specs.get(field_key)
    if not isinstance(field_spec, FieldIr):
        return extract_field(data, field_key)

    data_key = field_spec.extract_expr or field_spec.data_key or field_key
    value: FieldValue = extract_field_segments(data, field_spec.extract_segments)
    value_transform = exec_ctx.runtime.runtime_bindings.get_value_transform(field_spec.field_id)
    try:
        return value_transform(value) if value_transform is not None else value
    except Exception as exc:
        guardrails = exec_ctx.runtime.guardrails
        if not guardrails.enabled:
            raise
        handle_loader_transform_error(
            exec_ctx.runtime,
            source_id=source.source_id,
            row_id=row_id,
            field_key=field_key,
            data_key=data_key,
            exc=exc,
            mode=transform_mode,
            is_ref_loader=True,
            lookup_key=lookup_key,
        )
        return None


def _write_ref_fields(
    *,
    exec_ctx: LoadRefExecutionContext,
    source: LookupSourceRefIrBase,
    row_id: Hashable,
    lookup_key: LookupKey,
    data: object,
    group_field_keys: Tuple[str, ...],
    required_field_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> None:
    for field_key in group_field_keys:
        value = _resolve_ref_field_value(
            exec_ctx=exec_ctx,
            source=source,
            row_id=row_id,
            lookup_key=lookup_key,
            field_key=field_key,
            data=data,
            transform_mode=transform_mode,
        )
        exec_ctx.context.set_field_value(field_key, row_id, value)
        maybe_enforce_required_field_value(
            exec_ctx.runtime,
            source_id=source.source_id,
            row_id=row_id,
            field_key=field_key,
            value=value,
            required_field_keys=required_field_keys,
            mode=required_mode,
            reason="value is None",
            is_ref_loader=True,
            lookup_key=lookup_key,
        )


def _write_final_step_row(
    *,
    exec_ctx: LoadRefExecutionContext,
    row_id: Hashable,
    lookup_key: LookupKey,
    intermediate_result: LoaderResultMapping,
    source: LookupSourceRefIrBase,
    group_field_keys: Tuple[str, ...],
    required_field_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> None:
    if lookup_key not in intermediate_result:
        for field_key in group_field_keys:
            _write_relation_miss_field_value(
                exec_ctx,
                row_id,
                field_key=field_key,
                required_field_keys=required_field_keys,
                required_mode=required_mode,
                transform_mode=transform_mode,
                reason="lookup key not found in loader result",
                lookup_key=lookup_key,
            )
        return

    data = intermediate_result[lookup_key]
    data = _apply_ref_extractor(
        exec_ctx=exec_ctx,
        source=source,
        row_id=row_id,
        lookup_key=lookup_key,
        intermediate_result=intermediate_result,
        data=data,
        transform_mode=transform_mode,
    )
    _write_ref_fields(
        exec_ctx=exec_ctx,
        source=source,
        row_id=row_id,
        lookup_key=lookup_key,
        data=data,
        group_field_keys=group_field_keys,
        required_field_keys=required_field_keys,
        required_mode=required_mode,
        transform_mode=transform_mode,
    )


def write_final_step(
    exec_ctx: LoadRefExecutionContext,
    current_mapping: Dict[Hashable, LookupKey],
    intermediate_result: LoaderResultMapping,
    source: LookupSourceRefIrBase,
    group_field_keys: Tuple[str, ...],
) -> None:
    required_field_keys = _resolve_ref_required_field_keys(runtime=exec_ctx.runtime, group_field_keys=group_field_keys)
    guardrails = exec_ctx.runtime.guardrails
    required_mode = guardrails.mode
    transform_mode = guardrails.effective_loader_transform_mode()

    for row_id, fk_value in current_mapping.items():
        _write_final_step_row(
            exec_ctx=exec_ctx,
            row_id=row_id,
            lookup_key=fk_value,
            intermediate_result=intermediate_result,
            source=source,
            group_field_keys=group_field_keys,
            required_field_keys=required_field_keys,
            required_mode=required_mode,
            transform_mode=transform_mode,
        )


__all__ = (
    "build_next_mapping",
    "init_first_fk_mapping",
    "write_final_step",
)
