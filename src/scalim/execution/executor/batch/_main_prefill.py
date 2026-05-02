from typing import Callable, Hashable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from ....spec.ir import FieldIr
from ....typedefs import FieldValue, RowData
from ...context import BatchContext, DenseBatchContext
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


def _apply_main_source_value_transform(
    *,
    runtime: ExecutionRuntime,
    main_source_id: str,
    row_id: Hashable,
    field_key: str,
    data_key: str,
    value: FieldValue,
    value_transform: Callable[[FieldValue], FieldValue],
    transform_mode: str,
) -> FieldValue:
    try:
        return value_transform(value)
    except Exception as exc:
        if not runtime.guardrails.enabled:
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
        return None


def _resolve_dense_prefill_row_count(
    *,
    context: DenseBatchContext,
    batch_row_nth: Sequence[Hashable],
    main_rows: Sequence[RowData],
) -> int:
    return min(len(main_rows), len(batch_row_nth), int(context.dense_row_count()))


def _dense_prepare_rowwise_main_ops(
    *,
    context: DenseBatchContext,
    row_count: int,
    present_mask: bytes,
    main_field_ops: List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]],
    required_guardrail_keys: Set[str],
) -> Optional[
    List[
        Tuple[
            str,
            str,
            Tuple[Union[str, int], ...],
            Optional[Callable[[FieldValue], FieldValue]],
            List[FieldValue],
            bool,
            Optional[Callable[[str, Hashable], None]],
        ]
    ]
]:
    prepared_main: List[
        Tuple[
            str,
            str,
            Tuple[Union[str, int], ...],
            Optional[Callable[[FieldValue], FieldValue]],
            List[FieldValue],
            bool,
            Optional[Callable[[str, Hashable], None]],
        ]
    ] = []
    for field_key, data_key, segments, value_transform in main_field_ops:
        values = context.dense_prefill_prepare_storage(field_key, row_count=row_count, present_mask=present_mask)
        if values is None:
            return None
        prepared_main.append(
            (
                field_key,
                data_key,
                segments,
                value_transform,
                values,
                field_key in required_guardrail_keys,
                context.dense_on_field_set_callback_for_field(field_key),
            )
        )
    return prepared_main


def _dense_prepare_rowwise_passthrough_ops(
    *,
    context: DenseBatchContext,
    row_count: int,
    present_mask: bytes,
    passthrough_fields: List[str],
    required_guardrail_keys: Set[str],
) -> Optional[List[Tuple[str, List[FieldValue], bool, Optional[Callable[[str, Hashable], None]]]]]:
    prepared_passthrough: List[Tuple[str, List[FieldValue], bool, Optional[Callable[[str, Hashable], None]]]] = []
    for field_key in passthrough_fields:
        values = context.dense_prefill_prepare_storage(field_key, row_count=row_count, present_mask=present_mask)
        if values is None:
            return None
        prepared_passthrough.append(
            (
                field_key,
                values,
                field_key in required_guardrail_keys,
                context.dense_on_field_set_callback_for_field(field_key),
            )
        )
    return prepared_passthrough


def _dense_execute_rowwise_prefill(
    *,
    base: int,
    row_count: int,
    main_rows: Sequence[RowData],
    runtime: ExecutionRuntime,
    main_source_id: str,
    prepared_main: List[
        Tuple[
            str,
            str,
            Tuple[Union[str, int], ...],
            Optional[Callable[[FieldValue], FieldValue]],
            List[FieldValue],
            bool,
            Optional[Callable[[str, Hashable], None]],
        ]
    ],
    prepared_passthrough: List[Tuple[str, List[FieldValue], bool, Optional[Callable[[str, Hashable], None]]]],
    required_guardrail_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> None:
    extract_field_value = extract_field
    extract_field_value_segments = extract_field_segments
    enforce_required = maybe_enforce_required_field_value

    for idx in range(row_count):
        row_id = base + int(idx)
        row_data = main_rows[idx]

        for field_key, data_key, segments, value_transform, values, needs_required_check, on_field_set_cb in prepared_main:
            field_value: FieldValue = extract_field_value_segments(row_data, segments)
            if value_transform is not None:
                field_value = _apply_main_source_value_transform(
                    runtime=runtime,
                    main_source_id=main_source_id,
                    row_id=row_id,
                    field_key=field_key,
                    data_key=data_key,
                    value=field_value,
                    value_transform=value_transform,
                    transform_mode=transform_mode,
                )

            values[idx] = field_value
            if on_field_set_cb is not None:
                on_field_set_cb(field_key, row_id)
            if needs_required_check:
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

        for field_key, values, needs_required_check, on_field_set_cb in prepared_passthrough:
            field_value = extract_field_value(row_data, field_key)
            values[idx] = field_value
            if on_field_set_cb is not None:
                on_field_set_cb(field_key, row_id)
            if needs_required_check:
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


def _dense_prefill_rowwise(
    *,
    context: DenseBatchContext,
    base: int,
    row_count: int,
    present_mask: bytes,
    main_rows: Sequence[RowData],
    runtime: ExecutionRuntime,
    main_source_id: str,
    main_field_ops: List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]],
    passthrough_fields: List[str],
    required_guardrail_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> bool:
    # 注意: 为保证 `guardrails` 在 `fast_fail` 下的“首个违规”一致性,此处保持“按行优先”的执行顺序:
    # - 先处理第 0 行的所有字段,再处理第 1 行……
    #
    # 该顺序与通用 `BatchContext` 预填充路径保持一致。
    prepared_main = _dense_prepare_rowwise_main_ops(
        context=context,
        row_count=row_count,
        present_mask=present_mask,
        main_field_ops=main_field_ops,
        required_guardrail_keys=required_guardrail_keys,
    )
    if prepared_main is None:
        return False

    prepared_passthrough = _dense_prepare_rowwise_passthrough_ops(
        context=context,
        row_count=row_count,
        present_mask=present_mask,
        passthrough_fields=passthrough_fields,
        required_guardrail_keys=required_guardrail_keys,
    )
    if prepared_passthrough is None:
        return False

    _dense_execute_rowwise_prefill(
        base=base,
        row_count=row_count,
        main_rows=main_rows,
        runtime=runtime,
        main_source_id=main_source_id,
        prepared_main=prepared_main,
        prepared_passthrough=prepared_passthrough,
        required_guardrail_keys=required_guardrail_keys,
        required_mode=required_mode,
        transform_mode=transform_mode,
    )
    return True


def _prefill_main_source_fields_dense(
    *,
    context: DenseBatchContext,
    batch_row_nth: Sequence[Hashable],
    main_rows: Sequence[RowData],
    runtime: ExecutionRuntime,
    main_source_id: str,
    main_field_ops: List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]],
    passthrough_fields: List[str],
    required_guardrail_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> bool:
    row_count = _resolve_dense_prefill_row_count(context=context, batch_row_nth=batch_row_nth, main_rows=main_rows)
    if row_count <= 0:
        return True

    base = int(context.dense_base_row_id())

    # 预先准备“全 1 掩码”,避免逐行更新 `present` 计数.
    ones = b"\x01" * int(row_count)

    return _dense_prefill_rowwise(
        context=context,
        base=base,
        row_count=row_count,
        present_mask=ones,
        main_rows=main_rows,
        runtime=runtime,
        main_source_id=main_source_id,
        main_field_ops=main_field_ops,
        passthrough_fields=passthrough_fields,
        required_guardrail_keys=required_guardrail_keys,
        required_mode=required_mode,
        transform_mode=transform_mode,
    )


def _prefill_main_source_fields_generic(
    *,
    context: BatchContext,
    batch_row_nth: Sequence[Hashable],
    main_rows: Sequence[RowData],
    runtime: ExecutionRuntime,
    main_source_id: str,
    main_field_ops: List[Tuple[str, str, Tuple[Union[str, int], ...], Optional[Callable[[FieldValue], FieldValue]]]],
    passthrough_fields: List[str],
    required_guardrail_keys: Set[str],
    required_mode: str,
    transform_mode: str,
) -> None:
    context_set_field_value = context.set_field_value
    extract_field_value_segments = extract_field_segments
    extract_field_value = extract_field
    enforce_required = maybe_enforce_required_field_value

    row_count = min(len(main_rows), len(batch_row_nth))

    for idx in range(row_count):
        row_id = batch_row_nth[idx]
        row_data = main_rows[idx]
        for field_key, data_key, segments, value_transform in main_field_ops:
            field_value: FieldValue = extract_field_value_segments(row_data, segments)
            if value_transform is not None:
                field_value = _apply_main_source_value_transform(
                    runtime=runtime,
                    main_source_id=main_source_id,
                    row_id=row_id,
                    field_key=field_key,
                    data_key=data_key,
                    value=field_value,
                    value_transform=value_transform,
                    transform_mode=transform_mode,
                )
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


def prefill_main_source_fields(
    *,
    context: BatchContext,
    plan_field_specs: Mapping[str, object],
    runtime: ExecutionRuntime,
    batch_row_nth: Sequence[Hashable],
    main_rows: Optional[Sequence[RowData]],
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

    main_field_ops = _build_main_field_ops(main_field_specs=main_field_specs, get_value_transform=get_value_transform)

    # 快路径: `DenseBatchContext` + 连续 `row_id`,避免逐行调用 `set_field_value`.
    if isinstance(context, DenseBatchContext) and _prefill_main_source_fields_dense(
        context=context,
        batch_row_nth=batch_row_nth,
        main_rows=main_rows,
        runtime=runtime,
        main_source_id=main_source_id,
        main_field_ops=main_field_ops,
        passthrough_fields=passthrough_fields,
        required_guardrail_keys=required_guardrail_keys,
        required_mode=required_mode,
        transform_mode=transform_mode,
    ):
        return

    _prefill_main_source_fields_generic(
        context=context,
        batch_row_nth=batch_row_nth,
        main_rows=main_rows,
        runtime=runtime,
        main_source_id=main_source_id,
        main_field_ops=main_field_ops,
        passthrough_fields=passthrough_fields,
        required_guardrail_keys=required_guardrail_keys,
        required_mode=required_mode,
        transform_mode=transform_mode,
    )


__all__ = ()
