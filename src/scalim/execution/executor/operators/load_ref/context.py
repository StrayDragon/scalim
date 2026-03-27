from typing import Hashable, List, Optional

from .....spec.ir import LookupStepIr
from .....spec.ir._source_contracts import LookupSourceRefIrBase
from .....typedefs import DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY, LookupKey, RelationLookupResult, RowData
from .....utils.relation_signature import RelationSignature, is_auto_lookup_cast
from ....context import BatchContext
from ...helpers.batch_data import build_row
from ...helpers.field_access import contains_float
from ...runtime.runtime import ExecutionRuntime
from .._internal.sentinels import MISSING


class LoadRefExecutionContext:
    """`LoadRefOperatorExecutor` 的执行上下文,封装共享状态和辅助方法."""

    runtime: ExecutionRuntime
    context: BatchContext
    batch_row_nth: List[Hashable]
    field_key: str
    relation_signature: RelationSignature

    def __init__(
        self,
        runtime: ExecutionRuntime,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        field_key: str,
        relation_signature: RelationSignature,
    ) -> None:
        self.runtime = runtime
        self.context = context
        self.batch_row_nth = batch_row_nth
        self.field_key = field_key
        self.relation_signature = relation_signature

    def record_lookup(
        self,
        row_id: Hashable,
        fk_raw: object,
        fk_normalized: Optional[LookupKey],
        target_source: LookupSourceRefIrBase,
        result: RelationLookupResult,
        error_message: Optional[str] = None,
    ) -> None:
        fk_type = type(fk_raw).__name__ if fk_raw is not None else None
        self.runtime.instrumentation.emit_relation_lookup(
            field_key=self.field_key,
            row_id=row_id,
            fk_raw=fk_raw,
            fk_normalized=fk_normalized,
            target_source=target_source.source_id,
            result=result,  # type: ignore[arg-type]
            fk_type=fk_type,
            error_message=error_message,
        )

    def maybe_warn_float_lookup_key(self, row_id: Hashable, raw_key: object, step: LookupStepIr) -> None:
        if not is_auto_lookup_cast(step.lookup_cast):
            return
        if not contains_float(raw_key):
            return
        self.runtime.instrumentation.emit_diagnostic_warning(
            message=DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY,
            source_id=step.to_source.source_id,
            field_id=self.field_key,
            lookup_key=raw_key,
            row_id=row_id,
            sample_once=True,
        )

    def normalize_key(self, row_id: Hashable, raw_key: object, step: LookupStepIr) -> Optional[LookupKey]:
        relation_cache = self.runtime.key_normalize_cache.get(self.relation_signature)
        if relation_cache is None:
            relation_cache = {}
            self.runtime.key_normalize_cache[self.relation_signature] = relation_cache

        cache_key = (row_id, step.get_from_fields())
        cached = relation_cache.get(cache_key, MISSING)
        if cached is not MISSING:
            return cached

        self.maybe_warn_float_lookup_key(row_id, raw_key, step)
        normalized, status, error_message = self.runtime.normalize_lookup_key_with_status(raw_key, step)
        if status == "ok":
            relation_cache[cache_key] = normalized
            return normalized
        lookup_result = "null_key" if status == "null_key" else "type_error"
        self.record_lookup(row_id, raw_key, normalized, step.to_source, lookup_result, error_message)
        relation_cache[cache_key] = None
        return None

    def build_batch_rows(self) -> List[RowData]:
        field_keys = sorted(self.context.get_field_keys())
        return [build_row(self.context, row_id, field_keys) for row_id in self.batch_row_nth]


__all__ = [
    "LoadRefExecutionContext",
]
