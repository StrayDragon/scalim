import logging
from types import MappingProxyType
from typing import Any, Dict, Hashable, List, Tuple, cast

from .....events import EventType
from .....planning.operators import ComputeOperatorIr, SupportedOperatorIr
from .....spec.ir import ComputeCallContextIr, DerivedFieldIr
from .....vendor.compact.typing_extensionsx import override
from ....context import BatchContext, DenseBatchContext
from ...runtime.runtime import ExecutionRuntime
from ..base import OperatorExecutor
from .errors import handle_compute_error
from .payloads import build_field_compute_dependencies_payload

_EXPECTED_COMPUTE_ERRORS = (
    TypeError,
    ValueError,
    ZeroDivisionError,
    ArithmeticError,
)

_DEPS_LEN_ONE = 1
_DEPS_LEN_TWO = 2
_DEPS_LEN_THREE = 3


def _execute_row_compute_dense(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c0
    *,
    field_spec: DerivedFieldIr,
    context: DenseBatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
    compute_mode: str,
    wants_field_compute: bool,
) -> bool:
    deps: Tuple[str, ...] = tuple(field_spec.dependencies or ())
    deps_len = len(deps)
    calculator = runtime.runtime_bindings.require_derived_calculator(field_spec.field_id)
    value_transform = runtime.runtime_bindings.get_value_transform(field_spec.field_id)
    guardrails_enabled = runtime.guardrails.enabled
    use_ctx = field_spec.call_ctx_key is not None
    dep_cardinality = runtime.call_by_dep_cardinality
    if dep_cardinality is not None and (field_spec.call_by is None or use_ctx):
        dep_cardinality = None
    memoization = runtime.call_by_memoization
    memo_cache = None
    if memoization is not None and field_spec.call_by is not None and not use_ctx and memoization.is_field_allowed(field_spec.field_id):
        memo_cache = memoization.get_or_create_field_cache(field_spec.field_id)

    base_row_id = int(context.dense_base_row_id())
    row_count = int(context.dense_row_count())

    # `RowEmissionCoordinator` 可能在 `on_field_set` 回调内部触发 `flush` + `release`:
    # - 会删除当前字段的行值
    # - 当存储变空时可能把稠密存储从 `context` 中 `pop` 掉
    # 因此在本算子期间 `pin` 住输出字段存储,确保热循环持有的 `_DenseFieldStorage` 引用稳定.
    context.dense_pin_field_storage(field_spec.field_id)
    try:
        disabled_rows = context.dense_disabled_rows_or_none()

        out_storage = context.dense_prepare_write_storage(field_spec.field_id)
        if out_storage is None:
            return False
        out_values = out_storage.values
        out_present = out_storage.present
        on_field_set = context.dense_on_field_set_callback_for_field(field_spec.field_id)

        dep_storages = [context.dense_get_storage_for_read(dep_key) for dep_key in deps]

        # 注意: 该快路径仅在 `DenseBatchContext` 下启用; 若遇到非 `int` 或越界 `row_id`,直接回退通用实现.
        for row_id in batch_row_nth:
            if disabled_rows is not None and row_id in disabled_rows:
                continue
            if not isinstance(row_id, int):
                return False
            idx = int(row_id) - base_row_id
            if idx < 0 or idx >= row_count:
                return False

            dep_values_payload: Dict[str, Any] = {}
            d0: Any = None
            d1: Any = None
            d2: Any = None
            dep_args: Tuple[Any, ...] = ()

            try:
                if deps_len == _DEPS_LEN_ONE:
                    st0 = dep_storages[0]
                    if st0 is None or st0.present[idx] == 0:
                        d0 = None
                    else:
                        d0 = st0.values[idx]
                    if dep_cardinality is not None:
                        dep_cardinality.record(field_key=field_spec.field_id, dep_args=(d0,))
                    if use_ctx or wants_field_compute:
                        dep_values_payload = {deps[0]: d0}
                    if use_ctx:
                        ctx = ComputeCallContextIr(
                            row_id=row_id,
                            batch_num=runtime.batch_num,
                            field_id=field_spec.field_id,
                            deps=deps,
                            values=MappingProxyType(dep_values_payload),
                        )
                        result = calculator(d0, ctx=ctx)
                    else:
                        raw = None
                        if memo_cache is not None:
                            hit, cached, hashable = memo_cache.try_get(d0)
                            if hit:
                                raw = cached
                            else:
                                raw = calculator(d0)
                                if hashable:
                                    memo_cache.store_miss(key=d0, value=raw)
                        else:
                            raw = calculator(d0)
                        result = raw
                elif deps_len == _DEPS_LEN_TWO:
                    st0 = dep_storages[0]
                    st1 = dep_storages[1]
                    if st0 is None or st0.present[idx] == 0:
                        d0 = None
                    else:
                        d0 = st0.values[idx]
                    if st1 is None or st1.present[idx] == 0:
                        d1 = None
                    else:
                        d1 = st1.values[idx]
                    if dep_cardinality is not None:
                        dep_cardinality.record(field_key=field_spec.field_id, dep_args=(d0, d1))
                    if use_ctx or wants_field_compute:
                        dep_values_payload = {deps[0]: d0, deps[1]: d1}
                    if use_ctx:
                        ctx = ComputeCallContextIr(
                            row_id=row_id,
                            batch_num=runtime.batch_num,
                            field_id=field_spec.field_id,
                            deps=deps,
                            values=MappingProxyType(dep_values_payload),
                        )
                        result = calculator(d0, d1, ctx=ctx)
                    else:
                        key = (d0, d1)
                        raw = None
                        if memo_cache is not None:
                            hit, cached, hashable = memo_cache.try_get(key)
                            if hit:
                                raw = cached
                            else:
                                raw = calculator(d0, d1)
                                if hashable:
                                    memo_cache.store_miss(key=key, value=raw)
                        else:
                            raw = calculator(d0, d1)
                        result = raw
                elif deps_len == _DEPS_LEN_THREE:
                    st0 = dep_storages[0]
                    st1 = dep_storages[1]
                    st2 = dep_storages[2]
                    if st0 is None or st0.present[idx] == 0:
                        d0 = None
                    else:
                        d0 = st0.values[idx]
                    if st1 is None or st1.present[idx] == 0:
                        d1 = None
                    else:
                        d1 = st1.values[idx]
                    if st2 is None or st2.present[idx] == 0:
                        d2 = None
                    else:
                        d2 = st2.values[idx]
                    if dep_cardinality is not None:
                        dep_cardinality.record(field_key=field_spec.field_id, dep_args=(d0, d1, d2))
                    if use_ctx or wants_field_compute:
                        dep_values_payload = {deps[0]: d0, deps[1]: d1, deps[2]: d2}
                    if use_ctx:
                        ctx = ComputeCallContextIr(
                            row_id=row_id,
                            batch_num=runtime.batch_num,
                            field_id=field_spec.field_id,
                            deps=deps,
                            values=MappingProxyType(dep_values_payload),
                        )
                        result = calculator(d0, d1, d2, ctx=ctx)
                    else:
                        key = (d0, d1, d2)
                        raw = None
                        if memo_cache is not None:
                            hit, cached, hashable = memo_cache.try_get(key)
                            if hit:
                                raw = cached
                            else:
                                raw = calculator(d0, d1, d2)
                                if hashable:
                                    memo_cache.store_miss(key=key, value=raw)
                        else:
                            raw = calculator(d0, d1, d2)
                        result = raw
                else:
                    dep_args = tuple((None if st is None or st.present[idx] == 0 else st.values[idx]) for st in dep_storages)
                    if dep_cardinality is not None:
                        dep_cardinality.record(field_key=field_spec.field_id, dep_args=dep_args)
                    if use_ctx or wants_field_compute:
                        dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                    if use_ctx:
                        ctx = ComputeCallContextIr(
                            row_id=row_id,
                            batch_num=runtime.batch_num,
                            field_id=field_spec.field_id,
                            deps=deps,
                            values=MappingProxyType(dep_values_payload),
                        )
                        result = calculator(*dep_args, ctx=ctx)
                    else:
                        raw = None
                        if memo_cache is not None:
                            hit, cached, hashable = memo_cache.try_get(dep_args)
                            if hit:
                                raw = cached
                            else:
                                raw = calculator(*dep_args)
                                if hashable:
                                    memo_cache.store_miss(key=dep_args, value=raw)
                        else:
                            raw = calculator(*dep_args)
                        result = raw

                if value_transform is not None:
                    result = value_transform(result)

                if out_present[idx] == 0:
                    out_present[idx] = 1
                    out_storage.present_count += 1
                out_values[idx] = result

                if on_field_set is not None:
                    on_field_set(field_spec.field_id, row_id)

                if wants_field_compute:
                    runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_values_payload, result)
            except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
                deps_payload = {}
                if not guardrails_enabled:
                    if not dep_values_payload:
                        if deps_len == _DEPS_LEN_ONE:
                            dep_values_payload = {deps[0]: d0}
                        elif deps_len == _DEPS_LEN_TWO:
                            dep_values_payload = {deps[0]: d0, deps[1]: d1}
                        elif deps_len == _DEPS_LEN_THREE:
                            dep_values_payload = {deps[0]: d0, deps[1]: d1, deps[2]: d2}
                        else:
                            dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                    deps_payload = dep_values_payload
                handle_compute_error(
                    runtime,
                    context,
                    field_key=field_spec.field_id,
                    row_id=row_id,
                    dependencies=deps_payload,
                    dependency_names=deps,
                    exc=exc,
                    compute_mode=compute_mode,
                    unexpected=False,
                )
            except Exception as exc:
                logging.exception(  # noqa: LOG015
                    "字段计算发生未预期的异常: 字段=%s, 行标识=%s",
                    field_spec.field_id,
                    row_id,
                )
                deps_payload = {}
                if not guardrails_enabled:
                    if not dep_values_payload:
                        if deps_len == _DEPS_LEN_ONE:
                            dep_values_payload = {deps[0]: d0}
                        elif deps_len == _DEPS_LEN_TWO:
                            dep_values_payload = {deps[0]: d0, deps[1]: d1}
                        elif deps_len == _DEPS_LEN_THREE:
                            dep_values_payload = {deps[0]: d0, deps[1]: d1, deps[2]: d2}
                        else:
                            dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                    deps_payload = dep_values_payload
                handle_compute_error(
                    runtime,
                    context,
                    field_key=field_spec.field_id,
                    row_id=row_id,
                    dependencies=deps_payload,
                    dependency_names=deps,
                    exc=exc,
                    compute_mode=compute_mode,
                    unexpected=True,
                )

        return True
    finally:
        context.dense_unpin_field_storage(field_spec.field_id)


def _execute_constant_compute(
    *,
    field_spec: DerivedFieldIr,
    context: BatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
    compute_mode: str,
    wants_field_compute: bool,
) -> None:
    deps: Tuple[str, ...] = tuple(field_spec.dependencies or ())
    dep_payload: Dict[str, Any] = {}
    calculator = runtime.runtime_bindings.require_derived_calculator(field_spec.field_id)
    value_transform = runtime.runtime_bindings.get_value_transform(field_spec.field_id)

    try:
        result = calculator()
        if value_transform is not None:
            result = value_transform(result)
    except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
        for row_id in batch_row_nth:
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=dep_payload,
                dependency_names=deps,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=False,
            )
        return
    except Exception as exc:
        first_row_id = batch_row_nth[0] if batch_row_nth else None
        logging.exception(  # noqa: LOG015
            "字段计算发生未预期的异常: 字段=%s, 行标识=%s",
            field_spec.field_id,
            first_row_id,
        )
        for row_id in batch_row_nth:
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=dep_payload,
                dependency_names=deps,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=True,
            )
        return

    for row_id in batch_row_nth:
        context.set_field_value(field_spec.field_id, row_id, result)
        if wants_field_compute:
            runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_payload, result)


def _execute_row_compute(  # noqa: C901, PLR0912, PLR0915  # pragma: allow-c901 plan: c0
    *,
    field_spec: DerivedFieldIr,
    context: BatchContext,
    batch_row_nth: List[Hashable],
    runtime: ExecutionRuntime,
    compute_mode: str,
    wants_field_compute: bool,
) -> None:
    deps: Tuple[str, ...] = tuple(field_spec.dependencies or ())
    calculator = runtime.runtime_bindings.require_derived_calculator(field_spec.field_id)
    value_transform = runtime.runtime_bindings.get_value_transform(field_spec.field_id)
    guardrails_enabled = runtime.guardrails.enabled
    use_ctx = field_spec.call_ctx_key is not None
    dep_cardinality = runtime.call_by_dep_cardinality
    if dep_cardinality is not None and (field_spec.call_by is None or use_ctx):
        dep_cardinality = None
    memoization = runtime.call_by_memoization
    memo_cache = None
    if memoization is not None and field_spec.call_by is not None and not use_ctx and memoization.is_field_allowed(field_spec.field_id):
        memo_cache = memoization.get_or_create_field_cache(field_spec.field_id)

    if isinstance(context, DenseBatchContext) and _execute_row_compute_dense(
        field_spec=field_spec,
        context=context,
        batch_row_nth=batch_row_nth,
        runtime=runtime,
        compute_mode=compute_mode,
        wants_field_compute=wants_field_compute,
    ):
        return

    for row_id in batch_row_nth:
        dep_args: Tuple[Any, ...] = tuple(context.get_field_value(dep_key, row_id) for dep_key in deps)
        if dep_cardinality is not None:
            dep_cardinality.record(field_key=field_spec.field_id, dep_args=dep_args)
        dep_values_payload: Dict[str, Any] = {}
        if use_ctx or wants_field_compute:
            dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
        try:
            if use_ctx:
                ctx = ComputeCallContextIr(
                    row_id=row_id,
                    batch_num=runtime.batch_num,
                    field_id=field_spec.field_id,
                    deps=deps,
                    values=MappingProxyType(dep_values_payload),
                )
                result = calculator(*dep_args, ctx=ctx)
            else:
                raw = None
                if memo_cache is not None:
                    hit, cached, hashable = memo_cache.try_get(dep_args)
                    if hit:
                        raw = cached
                    else:
                        raw = calculator(*dep_args)
                        if hashable:
                            memo_cache.store_miss(key=dep_args, value=raw)
                else:
                    raw = calculator(*dep_args)
                result = raw
            if value_transform is not None:
                result = value_transform(result)
            context.set_field_value(field_spec.field_id, row_id, result)

            if wants_field_compute:
                runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_values_payload, result)
        except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
            deps_payload = {}
            if not guardrails_enabled:
                if not dep_values_payload:
                    dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                deps_payload = dep_values_payload
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=deps_payload,
                dependency_names=deps,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=False,
            )
        except Exception as exc:
            logging.exception(  # noqa: LOG015
                "字段计算发生未预期的异常: 字段=%s, 行标识=%s",
                field_spec.field_id,
                row_id,
            )
            deps_payload = {}
            if not guardrails_enabled:
                if not dep_values_payload:
                    dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                deps_payload = dep_values_payload
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=deps_payload,
                dependency_names=deps,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=True,
            )


class ComputeOperatorExecutor(OperatorExecutor):
    """计算算子执行器."""

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("ComputeOperatorIr", operator)  # pragma: allow-cast operator dispatch typed narrowing
        field_spec = runtime.field_specs.get(op.field_key)
        if not isinstance(field_spec, DerivedFieldIr):
            return
        guardrails = runtime.guardrails
        compute_mode = guardrails.effective_compute_mode()
        wants_field_compute = runtime.instrumentation.wants(EventType.FIELD_COMPUTE)

        if field_spec.is_constant_compute:
            _execute_constant_compute(
                field_spec=field_spec,
                context=context,
                batch_row_nth=batch_row_nth,
                runtime=runtime,
                compute_mode=compute_mode,
                wants_field_compute=wants_field_compute,
            )
            return

        _execute_row_compute(
            field_spec=field_spec,
            context=context,
            batch_row_nth=batch_row_nth,
            runtime=runtime,
            compute_mode=compute_mode,
            wants_field_compute=wants_field_compute,
        )


__all__ = ("ComputeOperatorExecutor",)
