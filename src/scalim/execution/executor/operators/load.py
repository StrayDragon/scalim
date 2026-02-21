import time
from collections.abc import Hashable, Mapping
from typing import Any, cast

from ....events.catalog import EVENT_LOADER_CALL, EVENT_LOADER_SLIM
from ....planning.operators import LoadOperatorIr, SupportedOperatorIr
from ....spec.ir.binding import BindingIr, LoaderCallContextIr
from ....spec.ir.fields import FieldIr
from ....spec.ir.helpers import call_loader_with_binding
from ....spec.ir.sources import SourceIr
from ....typedefs import FieldValue
from ....vendor.compact.typing_extensionsx import override
from ...context import BatchContext
from ..guardrails import build_loader_result_guardrail_payload, fail_guardrail
from ..helpers.field_access import extract_field
from ..runtime.runtime import ExecutionRuntime
from ._internal.loader_guardrails import (
    handle_loader_extractor_error,
    handle_loader_transform_error,
    maybe_enforce_required_field_value,
    record_or_fail_required_field_missing,
)
from ._internal.sentinels import MISSING
from .base import OperatorExecutor


class LoadOperatorExecutor(OperatorExecutor):
    """加载算子执行器"""

    def _build_loader_call_kwargs(
        self,
        runtime: "ExecutionRuntime",
        binding: BindingIr | None,
        loader_context: LoaderCallContextIr,
    ) -> dict[str, Any]:
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
        result: Any,
        field_keys: list[str],
    ) -> None:
        if not runtime.instrumentation.wants(EVENT_LOADER_SLIM):
            return
        original_keys = 0
        if isinstance(result, dict) and result:
            result_dict = cast("dict[Any, Any]", result)
            sample_value: Any = next(iter(result_dict.values()))
            if isinstance(sample_value, dict):
                sample_dict = cast("dict[Any, Any]", sample_value)
                original_keys = len(sample_dict)
        if original_keys and original_keys > len(field_keys):
            runtime.instrumentation.emit_loader_slim(
                loader_name=loader_name,
                original_keys=original_keys,
                extracted_fields=field_keys,
                batch_num=runtime.batch_num,
            )

    def _resolve_required_field_keys(self, runtime: ExecutionRuntime, field_keys: list[str]) -> set[str]:
        guardrails = runtime.guardrails
        if guardrails.enabled and guardrails.loader.required_fields:
            return set(field_keys) & set(guardrails.loader.required_fields)
        return set()

    def _extract_row_data(
        self,
        *,
        runtime: ExecutionRuntime,
        source: SourceIr,
        result: Any,
        row_id: Hashable,
        required_field_keys: set[str],
        required_mode: str,
        transform_mode: str,
    ) -> Any:
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
        data: Any,
        transform_mode: str,
    ) -> FieldValue:
        field_spec = runtime.field_specs.get(field_key)
        if not isinstance(field_spec, FieldIr):
            return extract_field(data, field_key)

        data_key = field_spec.data_key or field_key
        value: FieldValue = extract_field(data, data_key)
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
        data: Any,
        field_keys: list[str],
        required_field_keys: set[str],
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
        field_keys: list[str],
        batch_row_nth: list[Hashable],
        result: Any,
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
        batch_row_nth: list[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        op = cast("LoadOperatorIr", operator)
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
        result = call_loader_with_binding(binding, loader_context, loader_fn)
        loader_duration = time.perf_counter() - loader_start

        call_kwargs = self._build_loader_call_kwargs(runtime, binding, loader_context)
        runtime.instrumentation.emit_loader_call(source.source_id, call_kwargs, result, loader_duration)
        self._maybe_emit_loader_slim(runtime, loader_name=source.source_id, result=result, field_keys=field_keys)

        guardrails = runtime.guardrails
        if guardrails.enabled and guardrails.loader.validate_result and not isinstance(result, Mapping):
            fail_guardrail(
                runtime,
                code="loader_result_not_mapping",
                message="Loader result must be a Mapping",
                context=build_loader_result_guardrail_payload(runtime, source_id=source.source_id, result=result),
                action_mode="fast_fail",
            )
        self._process_loader_rows(
            context=context,
            runtime=runtime,
            source=source,
            field_keys=field_keys,
            batch_row_nth=batch_row_nth,
            result=result,
        )
