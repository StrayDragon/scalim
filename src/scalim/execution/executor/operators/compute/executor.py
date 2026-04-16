import logging
from typing import Any, Dict, Hashable, List, Tuple, cast

from .....events import EventType
from .....planning.operators import ComputeOperatorIr, SupportedOperatorIr
from .....spec.ir import ComputeCallContextIr, DerivedFieldIr
from .....vendor.compact.typing_extensionsx import override
from ....context import BatchContext
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


def _execute_row_compute(
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

    for row_id in batch_row_nth:
        dep_args: Tuple[Any, ...] = tuple(context.get_field_value(dep_key, row_id) for dep_key in deps)
        try:
            if use_ctx:
                dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                ctx = ComputeCallContextIr(
                    row_id=row_id,
                    batch_num=runtime.batch_num,
                    field_id=field_spec.field_id,
                    deps=deps,
                    values=dep_values_payload,
                )
                result = calculator(*dep_args, ctx=ctx)
            else:
                result = calculator(*dep_args)
            if value_transform is not None:
                result = value_transform(result)
            context.set_field_value(field_spec.field_id, row_id, result)

            if wants_field_compute:
                dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_values_payload, result)
        except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
            deps_payload: Dict[str, Any] = {}
            if not guardrails_enabled:
                deps_payload = build_field_compute_dependencies_payload(deps, dep_args)
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
                deps_payload = build_field_compute_dependencies_payload(deps, dep_args)
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
