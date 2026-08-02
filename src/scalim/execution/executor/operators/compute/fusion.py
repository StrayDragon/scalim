"""行内 `compute` 融合 (`c20`): 同 `deps` 组按行一次读依赖、依次算字段.

仅作用于仍在 `compute` 段求值的字段;`late_fields` 由 `write-precompute` 跳过.
安全外壳外回退 `field-major`(由调用方决定).
"""

# region imports

import logging
from typing import AbstractSet, Any, Callable, Collection, Dict, Hashable, List, Optional, Sequence, Tuple

from .....events import EventType
from .....planning.builder_helpers.fusion_groups import ComputeFusionGroup
from .....sinks import IColumnSink
from .....spec.ir import DerivedFieldIr
from .....typedefs import FieldValue
from .....vendor.compact.typing_extensionsx import Protocol
from ....context import BatchContext, DenseBatchContext
from ...runtime.runtime import ExecutionRuntime
from .errors import handle_compute_error
from .payloads import build_field_compute_dependencies_payload

# endregion

_EXPECTED_COMPUTE_ERRORS = (
    TypeError,
    ValueError,
    ZeroDivisionError,
    ArithmeticError,
)

_DEPS_LEN_ONE = 1
_DEPS_LEN_TWO = 2


class _DenseStorageView(Protocol):
    """稠密字段存储的只读/写出视图(避免跨模块依赖私有 `_DenseFieldStorage`)."""

    values: List[FieldValue]
    present: bytearray
    present_count: int


def fusion_disabled_reason(
    runtime: ExecutionRuntime,
    group: ComputeFusionGroup,
    active_field_keys: Sequence[str],
) -> Optional[str]:
    """返回禁用原因码;`None` 表示可融合.

    `fast_fail` 仅在 `guardrails` **启用**且有效 `compute` 模式为 `fast_fail` 时禁用
    (默认 `enabled=False` 时仍可融合,否则默认永远无法命中 `ROI`).
    """
    del group  # 组级诊断预留;当前仅用成员列表
    sink = runtime.sink
    if sink is not None and isinstance(sink, IColumnSink):
        return "column_sink"

    instrumentation = runtime.instrumentation
    if instrumentation.wants(EventType.FIELD_COMPUTE) or instrumentation.wants(EventType.OPERATOR_SPAN):
        return "wants_events"

    guardrails = runtime.guardrails
    if guardrails.enabled and guardrails.effective_compute_mode() == "fast_fail":
        return "fast_fail"

    memoization = runtime.call_by_memoization
    if memoization is not None:
        for field_key in active_field_keys:
            field_spec = runtime.field_specs.get(field_key)
            if not isinstance(field_spec, DerivedFieldIr):
                continue
            if field_spec.call_by is None or field_spec.call_ctx_key is not None:
                continue
            if memoization.is_field_allowed(field_key):
                return "memo"
    return None


def active_fusion_members(group: ComputeFusionGroup, late_fields: Collection[str]) -> Tuple[str, ...]:
    """去掉当前 `runtime` `late` 后的组员(写出路径跳过 `late`)."""
    if not late_fields:
        return group.field_keys
    late_set: AbstractSet[str]
    if isinstance(late_fields, (set, frozenset)):
        late_set = late_fields
    else:
        late_set = set(late_fields)
    return tuple(fk for fk in group.field_keys if fk not in late_set)


def _execute_fused_dense(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c20-fused-dense
    *,
    group: ComputeFusionGroup,
    field_plans: Sequence[Tuple[str, Any, Any]],
    context: DenseBatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
) -> bool:
    """稠密批次快路径: 按 `idx` 读 `deps` 一次,再写多字段."""
    deps = group.deps
    compute_mode = runtime.guardrails.effective_compute_mode()
    guardrails_enabled = runtime.guardrails.enabled
    base_row_id = int(context.dense_base_row_id())
    row_count = int(context.dense_row_count())
    disabled_rows = context.dense_disabled_rows_or_none()

    pinned = [fk for fk, _, _ in field_plans]
    for field_key in pinned:
        context.dense_pin_field_storage(field_key)
    try:
        out_storages: List[_DenseStorageView] = []
        on_sets: List[Optional[Callable[[str, Hashable], None]]] = []
        for field_key, _, _ in field_plans:
            # `dense_*` 返回私有存储类型;经 `Any` 桥接到本地 `Protocol` 视图.
            storage_any: Any = context.dense_prepare_write_storage(field_key)
            if storage_any is None:
                return False
            storage: _DenseStorageView = storage_any
            out_storages.append(storage)
            on_sets.append(context.dense_on_field_set_callback_for_field(field_key))

        dep_storages: List[Optional[_DenseStorageView]] = []
        for dep_key in deps:
            dep_any: Any = context.dense_get_storage_for_read(dep_key)
            dep_storages.append(None if dep_any is None else dep_any)

        deps_len = len(deps)

        for row_id in batch_row_nth:
            if disabled_rows is not None and row_id in disabled_rows:
                continue
            if not isinstance(row_id, int):
                return False
            idx = int(row_id) - base_row_id
            if idx < 0 or idx >= row_count:
                return False

            dep_args: Tuple[FieldValue, ...]
            if deps_len == _DEPS_LEN_ONE:
                st0 = dep_storages[0]
                d0: FieldValue = None if st0 is None or st0.present[idx] == 0 else st0.values[idx]
                dep_args = (d0,)
            elif deps_len == _DEPS_LEN_TWO:
                st0 = dep_storages[0]
                st1 = dep_storages[1]
                d0 = None if st0 is None or st0.present[idx] == 0 else st0.values[idx]
                d1: FieldValue = None if st1 is None or st1.present[idx] == 0 else st1.values[idx]
                dep_args = (d0, d1)
            else:
                args_list: List[FieldValue] = []
                for st in dep_storages:
                    if st is None or st.present[idx] == 0:
                        args_list.append(None)
                    else:
                        args_list.append(st.values[idx])
                dep_args = tuple(args_list)

            dep_payload: Optional[Dict[str, Any]] = None
            for i, (field_key, calculator, value_transform) in enumerate(field_plans):
                try:
                    result = calculator(*dep_args)
                    if value_transform is not None:
                        result = value_transform(result)
                    out = out_storages[i]
                    # `present_count` 必须与 `present` 位同步维护: 行级释放按该计数回收存储.
                    if out.present[idx] == 0:
                        out.present[idx] = 1
                        out.present_count += 1
                    out.values[idx] = result
                    on_set = on_sets[i]
                    if on_set is not None:
                        on_set(field_key, row_id)
                except _EXPECTED_COMPUTE_ERRORS as exc:  # noqa: PERF203  # type: ignore[misc]
                    if dep_payload is None and not guardrails_enabled:
                        dep_payload = build_field_compute_dependencies_payload(deps, dep_args)
                    handle_compute_error(
                        runtime,
                        context,
                        field_key=field_key,
                        row_id=row_id,
                        dependencies=dep_payload or {},
                        dependency_names=deps,
                        exc=exc,
                        compute_mode=compute_mode,
                        unexpected=False,
                    )
                except Exception as exc:
                    logging.exception(  # noqa: LOG015
                        "字段计算发生未预期的异常: 字段=%s, 行标识=%s",
                        field_key,
                        row_id,
                    )
                    if dep_payload is None and not guardrails_enabled:
                        dep_payload = build_field_compute_dependencies_payload(deps, dep_args)
                    handle_compute_error(
                        runtime,
                        context,
                        field_key=field_key,
                        row_id=row_id,
                        dependencies=dep_payload or {},
                        dependency_names=deps,
                        exc=exc,
                        compute_mode=compute_mode,
                        unexpected=True,
                    )
        return True
    finally:
        for field_key in pinned:
            context.dense_unpin_field_storage(field_key)


def execute_fused_compute_group(  # noqa: C901  # pragma: allow-c901 plan: c20-fused-fallback
    *,
    group: ComputeFusionGroup,
    field_keys: Sequence[str],
    context: BatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
) -> None:
    """对 `field_keys`(`size>=2`) 执行行内融合;依赖读取一次/行."""
    deps = group.deps
    compute_mode = runtime.guardrails.effective_compute_mode()
    guardrails_enabled = runtime.guardrails.enabled
    field_plans: List[Tuple[str, Any, Any]] = []

    for field_key in field_keys:
        field_spec = runtime.field_specs.get(field_key)
        if not isinstance(field_spec, DerivedFieldIr):
            return
        calculator = runtime.runtime_bindings.require_derived_calculator(field_key)
        value_transform = runtime.runtime_bindings.get_value_transform(field_key)
        field_plans.append((field_key, calculator, value_transform))

    if isinstance(context, DenseBatchContext) and _execute_fused_dense(
        group=group,
        field_plans=field_plans,
        context=context,
        batch_row_nth=batch_row_nth,
        runtime=runtime,
    ):
        return

    for row_id in batch_row_nth:
        dep_args = tuple(context.get_field_value(dep, row_id) for dep in deps)
        dep_payload: Optional[Dict[str, Any]] = None

        for field_key, calculator, value_transform in field_plans:
            try:
                result = calculator(*dep_args)
                if value_transform is not None:
                    result = value_transform(result)
                context.set_field_value(field_key, row_id, result)
            except _EXPECTED_COMPUTE_ERRORS as exc:  # noqa: PERF203  # type: ignore[misc]
                if dep_payload is None and not guardrails_enabled:
                    dep_payload = build_field_compute_dependencies_payload(deps, dep_args)
                handle_compute_error(
                    runtime,
                    context,
                    field_key=field_key,
                    row_id=row_id,
                    dependencies=dep_payload or {},
                    dependency_names=deps,
                    exc=exc,
                    compute_mode=compute_mode,
                    unexpected=False,
                )
            except Exception as exc:
                logging.exception(  # noqa: LOG015
                    "字段计算发生未预期的异常: 字段=%s, 行标识=%s",
                    field_key,
                    row_id,
                )
                if dep_payload is None and not guardrails_enabled:
                    dep_payload = build_field_compute_dependencies_payload(deps, dep_args)
                handle_compute_error(
                    runtime,
                    context,
                    field_key=field_key,
                    row_id=row_id,
                    dependencies=dep_payload or {},
                    dependency_names=deps,
                    exc=exc,
                    compute_mode=compute_mode,
                    unexpected=True,
                )


__all__ = (
    "active_fusion_members",
    "execute_fused_compute_group",
    "fusion_disabled_reason",
)
