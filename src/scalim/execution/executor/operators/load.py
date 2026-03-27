import time
from collections.abc import Mapping
from typing import Hashable, List, Optional, Set
from typing import Mapping as TypingMapping

from ....events import EVENT_LOADER_CALL, EVENT_LOADER_SLIM
from ....planning.operators import LoadOperatorIr, SupportedOperatorIr
from ....spec.ir import FieldIr, SourceIr
from ....spec.ir._helpers import call_loader_with_binding, coerce_loader_result_mapping
from ....spec.ir.binding import BindingIr, LoaderCallContextIr
from ....typedefs import FieldValue, LoaderCallKwargs, LoaderResultMapping
from ....vendor.compact.typing_extensionsx import TypeGuard, override
from ...context import BatchContext
from ...loader_retry import CALLSITE_LOAD, call_with_loader_retry
from ..guardrails import build_loader_result_guardrail_payload, fail_guardrail
from ..helpers.field_access import extract_field, extract_field_segments
from ..runtime.runtime import ExecutionRuntime
from ._internal.loader_guardrails import (
    handle_loader_extractor_error,
    handle_loader_transform_error,
    maybe_enforce_required_field_value,
    record_or_fail_required_field_missing,
)
from ._internal.sentinels import MISSING
from .base import OperatorExecutor


def _is_mapping(value: object) -> TypeGuard[TypingMapping[object, object]]:
    return isinstance(value, Mapping)


class LoadOperatorExecutor(OperatorExecutor):
    """加载算子执行器"""

    def _build_loader_call_kwargs(
        self,
        runtime: "ExecutionRuntime",
        binding: Optional[BindingIr],
        loader_context: LoaderCallContextIr,
    ) -> LoaderCallKwargs:
        if binding is None:
            return {}
        if not runtime.instrumentation.wants(EVENT_LOADER_CALL):
            return {}
        _, call_kwargs = binding.build_params(loader_context)
        return call_kwargs

    def _maybe_emit_loader_slim(
        self,
        runtime: "ExecutionRuntime",
        *,
        loader_name: str,
        result: object,
        field_keys: List[str],
    ) -> None:
        if not runtime.instrumentation.wants(EVENT_LOADER_SLIM):
            return
        original_keys = 0
        if isinstance(result, Mapping) and result:
            sample_value = next(iter(result.values()))
            if _is_mapping(sample_value):
                original_keys = len(sample_value)
        if original_keys and original_keys > len(field_keys):
            runtime.instrumentation.emit_loader_slim(
                loader_name=loader_name,
                original_keys=original_keys,
                extracted_fields=field_keys,
                batch_num=runtime.batch_num,
            )

    def _resolve_required_field_keys(self, runtime: ExecutionRuntime, field_keys: List[str]) -> Set[str]:
        guardrails = runtime.guardrails
        if guardrails.enabled and guardrails.loader.required_fields:
            return set(field_keys) & set(guardrails.loader.required_fields)
        return set()

    def _extract_row_data(
        self,
        *,
        runtime: ExecutionRuntime,
        source: SourceIr,
        result: LoaderResultMapping,
        row_id: Hashable,
        required_field_keys: Set[str],
        required_mode: str,
        transform_mode: str,
    ) -> object:
        if row_id not in result:
            for required_field_key in required_field_keys:
                record_or_fail_required_field_missing(
                    runtime,
                    source_id=source.source_id,
                    row_id=row_id,
                    field_key=required_field_key,
                    reason="row_id not in loader result",
                    mode=required_mode,
                )
            return MISSING

        data = result[row_id]
        extractor = source.loader_spec.extractor
        if extractor is None:
            return data

        try:
            return extractor(row_id, result)
        except Exception as exc:
            guardrails = runtime.guardrails
            if not guardrails.enabled:
                raise
            handle_loader_extractor_error(
                runtime,
                source_id=source.source_id,
                row_id=row_id,
                exc=exc,
                mode=transform_mode,
            )
            return None

    def _resolve_field_value(
        self,
        *,
        runtime: ExecutionRuntime,
        source: SourceIr,
        row_id: Hashable,
        field_key: str,
        data: object,
        transform_mode: str,
    ) -> FieldValue:
        field_spec = runtime.field_specs.get(field_key)
        if not isinstance(field_spec, FieldIr):
            return extract_field(data, field_key)

        data_key = field_spec.extract_expr or field_spec.data_key or field_key
        value: FieldValue = extract_field_segments(data, field_spec.extract_segments)
        try:
            return field_spec.apply_transform(value)
        except Exception as exc:
            guardrails = runtime.guardrails
            if not guardrails.enabled:
                raise
            handle_loader_transform_error(
                runtime,
                source_id=source.source_id,
                row_id=row_id,
                field_key=field_key,
                data_key=data_key,
                exc=exc,
                mode=transform_mode,
            )
            return None

    def _write_row_fields(
        self,
        *,
        context: BatchContext,
        runtime: ExecutionRuntime,
        source: SourceIr,
        row_id: Hashable,
        data: object,
        field_keys: List[str],
        required_field_keys: Set[str],
        required_mode: str,
        transform_mode: str,
    ) -> None:
        for field_key in field_keys:
            value = self._resolve_field_value(
                runtime=runtime,
                source=source,
                row_id=row_id,
                field_key=field_key,
                data=data,
                transform_mode=transform_mode,
            )
            context.set_field_value(field_key, row_id, value)
            maybe_enforce_required_field_value(
                runtime,
                source_id=source.source_id,
                row_id=row_id,
                field_key=field_key,
                value=value,
                required_field_keys=required_field_keys,
                mode=required_mode,
                reason="value is None",
            )

    def _process_loader_rows(
        self,
        *,
        context: BatchContext,
        runtime: ExecutionRuntime,
        source: SourceIr,
        field_keys: List[str],
        batch_row_nth: List[Hashable],
        result: LoaderResultMapping,
    ) -> None:
        guardrails = runtime.guardrails
        required_field_keys = self._resolve_required_field_keys(runtime, field_keys)
        required_mode = guardrails.mode
        transform_mode = guardrails.effective_loader_transform_mode()

        for row_id in batch_row_nth:
            data = self._extract_row_data(
                runtime=runtime,
                source=source,
                result=result,
                row_id=row_id,
                required_field_keys=required_field_keys,
                required_mode=required_mode,
                transform_mode=transform_mode,
            )
            if data is MISSING:
                for field_key in field_keys:
                    context.set_field_value(field_key, row_id, None)
                continue
            self._write_row_fields(
                context=context,
                runtime=runtime,
                source=source,
                row_id=row_id,
                data=data,
                field_keys=field_keys,
                required_field_keys=required_field_keys,
                required_mode=required_mode,
                transform_mode=transform_mode,
            )

    @override
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        if not isinstance(operator, LoadOperatorIr):
            return

        op = operator
        source = op.source
        field_keys = list(op.field_keys)

        loader_context = LoaderCallContextIr(
            batch_row_nth=batch_row_nth,
            source_id=source.source_id,
            field_keys=field_keys,
            is_ref_loader=False,
        )

        key_field = source.key.key
        binding = source.get_binding(key_field)
        loader_fn = source.loader_spec.callable

        loader_start = time.perf_counter()
        policy = runtime.loader_retry.resolve(source.source_id)
        result_raw: object = call_with_loader_retry(
            call=lambda: call_loader_with_binding(binding, loader_context, loader_fn),
            instrumentation=runtime.instrumentation,
            policy=policy,
            loader_name=source.source_id,
            callsite=CALLSITE_LOAD,
            batch_num=runtime.batch_num,
        )
        loader_duration = time.perf_counter() - loader_start

        result_obj: object = result_raw
        if source.normalize is not None:
            result_obj = source.normalize.apply(result_raw, source_id=source.source_id)

        call_kwargs = self._build_loader_call_kwargs(runtime, binding, loader_context)
        runtime.instrumentation.emit_loader_call(source.source_id, call_kwargs, result_obj, loader_duration)
        self._maybe_emit_loader_slim(runtime, loader_name=source.source_id, result=result_obj, field_keys=field_keys)

        guardrails = runtime.guardrails
        is_mapping = isinstance(result_obj, Mapping)
        if guardrails.enabled and guardrails.loader.validate_result and not is_mapping:
            fail_guardrail(
                runtime,
                code="loader_result_not_mapping",
                message="Loader result must be a Mapping",
                context=build_loader_result_guardrail_payload(runtime, source_id=source.source_id, result=result_obj),
                action_mode="fast_fail",
            )
        result = coerce_loader_result_mapping(result_obj)
        self._process_loader_rows(
            context=context,
            runtime=runtime,
            source=source,
            field_keys=field_keys,
            batch_row_nth=batch_row_nth,
            result=result,
        )


__all__ = []
