import logging
from collections.abc import Hashable
from typing import Any, cast

from .....events.catalog import EVENT_FIELD_COMPUTE
from .....planning.operators import ComputeOperatorIr, SupportedOperatorIr
from .....spec.ir.fields import ComputeCallContextIr, DerivedFieldIr
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
    field_spec: "DerivedFieldIr",
    context: BatchContext,
    batch_row_nth: list[Hashable],
    runtime: ExecutionRuntime,
    *,
    compute_mode: str,
    wants_field_compute: bool,
) -> None:
    constant_dep_values: dict[str, Any] = {}
    try:
        result = field_spec.compute(**constant_dep_values)
    except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
        for row_id in batch_row_nth:
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=constant_dep_values,
                dependency_names=field_spec.dependencies,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=False,
            )
        return
    except Exception as exc:
        first_row_id = batch_row_nth[0] if batch_row_nth else None
        logging.exception(  # noqa: LOG015
            "Unexpected error in field computation: field=%s, row_id=%s",
            field_spec.field_id,
            first_row_id,
        )
        for row_id in batch_row_nth:
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=constant_dep_values,
                dependency_names=field_spec.dependencies,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=True,
            )
        return

    for row_id in batch_row_nth:
        context.set_field_value(field_spec.field_id, row_id, result)
        if wants_field_compute:
            runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, constant_dep_values, result)


def _execute_secure_compute(
    field_spec: "DerivedFieldIr",
    context: BatchContext,
    batch_row_nth: list[Hashable],
    runtime: ExecutionRuntime,
    *,
    compute_mode: str,
    wants_field_compute: bool,
) -> None:
    deps = field_spec.dependencies
    calculator = field_spec.calculator
    value_formatter = field_spec.value_formatter
    guardrails_enabled = runtime.guardrails.enabled

    for row_id in batch_row_nth:
        dep_args: tuple[Any, ...] = tuple(context.get_field_value(dep_key, row_id) for dep_key in deps)

        try:
            result = calculator(*dep_args)
            if value_formatter is not None:
                result = value_formatter(result)
            context.set_field_value(field_spec.field_id, row_id, result)

            if wants_field_compute:
                dep_values_payload = build_field_compute_dependencies_payload(deps, dep_args)
                runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_values_payload, result)
        except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
            deps_payload: dict[str, Any] = {}
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
                "Unexpected error in field computation: field=%s, row_id=%s",
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


def _execute_general_compute(
    field_spec: Any,
    context: BatchContext,
    batch_row_nth: list[Hashable],
    runtime: ExecutionRuntime,
    *,
    compute_mode: str,
    wants_field_compute: bool,
) -> None:
    for row_id in batch_row_nth:
        dep_values: dict[str, Any] = {}
        for dep_key in field_spec.dependencies:
            dep_values[dep_key] = context.get_field_value(dep_key, row_id)

        try:
            ctx_key = field_spec.call_ctx_key if isinstance(field_spec, DerivedFieldIr) else None
            if ctx_key:
                ctx_value = ComputeCallContextIr(
                    row_id=row_id,
                    batch_num=runtime.batch_num,
                    field_id=field_spec.field_id,
                    deps=field_spec.dependencies,
                    values=dep_values,
                )
                if wants_field_compute:
                    compute_kwargs = dict(dep_values)
                    compute_kwargs[ctx_key] = ctx_value
                    result = field_spec.compute(**compute_kwargs)
                else:
                    dep_values[ctx_key] = ctx_value
                    try:
                        result = field_spec.compute(**dep_values)
                    finally:
                        del dep_values[ctx_key]
            else:
                result = field_spec.compute(**dep_values)

            context.set_field_value(field_spec.field_id, row_id, result)
            if wants_field_compute:
                runtime.instrumentation.emit_field_compute(field_spec.field_id, row_id, dep_values, result)
        except _EXPECTED_COMPUTE_ERRORS as exc:  # type: ignore[misc]
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=dep_values,
                dependency_names=field_spec.dependencies,
                exc=exc,
                compute_mode=compute_mode,
                unexpected=False,
            )
        except Exception as exc:
            logging.exception(  # noqa: LOG015
                "Unexpected error in field computation: field=%s, row_id=%s",
                field_spec.field_id,
                row_id,
            )
            handle_compute_error(
                runtime,
                context,
                field_key=field_spec.field_id,
                row_id=row_id,
                dependencies=dep_values,
                dependency_names=field_spec.dependencies,
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
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("ComputeOperatorIr", operator)
        field_spec = op.field_spec
        guardrails = runtime.guardrails
        compute_mode = guardrails.effective_compute_mode()
        wants_field_compute = runtime.instrumentation.wants(EVENT_FIELD_COMPUTE)

        if field_spec.is_constant_compute:
            _execute_constant_compute(
                field_spec,
                context,
                batch_row_nth,
                runtime,
                compute_mode=compute_mode,
                wants_field_compute=wants_field_compute,
            )
            return

        if not field_spec.call_ctx_key and bool(getattr(field_spec.calculator, "_scalim_secure_compute", False)):
            _execute_secure_compute(
                field_spec,
                context,
                batch_row_nth,
                runtime,
                compute_mode=compute_mode,
                wants_field_compute=wants_field_compute,
            )
            return

        _execute_general_compute(
            field_spec,
            context,
            batch_row_nth,
            runtime,
            compute_mode=compute_mode,
            wants_field_compute=wants_field_compute,
        )


__all__ = [
    "ComputeOperatorExecutor",
]
