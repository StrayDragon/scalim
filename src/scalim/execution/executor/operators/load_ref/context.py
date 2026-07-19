from typing import Dict, Hashable, List, Optional, Tuple

from .....spec.ir import LookupStepIr
from .....spec.ir._source_contracts import LookupSourceRefIrBase
from .....typedefs import DIAGNOSTIC_WARNING_FLOAT_LOOKUP_KEY, LookupKey, RelationLookupResult, RowData, RuntimeValue
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
    default_applied_counts: Dict[str, int]

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
        self.default_applied_counts = {}

    def record_default_applied(self, field_key: str) -> None:
        key = str(field_key)
        # `NOTE:` `default_applied_counts` 在 `parallel_mode="adaptive"` 下可能被多个工作线程读写。
        # `NOTE:` 这里的 `read-modify-write`(`get()+1`) 并非原子语义;当前依赖 `CPython` `GIL` 的实现细节避免内存破坏。
        # `WARN:` `free-threaded`/`no-GIL` 的 `Python` 不在支持范围内;若要支持,需要显式锁或等价同步策略。
        self.default_applied_counts[key] = int(self.default_applied_counts.get(key, 0)) + 1

    def record_lookup(
        self,
        row_id: Hashable,
        fk_raw: RuntimeValue,
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

    def maybe_warn_float_lookup_key(self, row_id: Hashable, raw_key: RuntimeValue, step: LookupStepIr) -> None:
        effective_cast = step.lookup_cast if step.lookup_cast is not None else step.to_source.key.cast
        if not is_auto_lookup_cast(effective_cast):
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

    def normalize_key(
        self,
        row_id: Hashable,
        raw_key: RuntimeValue,
        step: LookupStepIr,
        *,
        from_fields: Optional[Tuple[str, ...]] = None,
    ) -> Optional[LookupKey]:
        if from_fields is None:
            from_fields = step.get_from_fields()

        # `NOTE:` `key_normalize_cache` 在 `parallel_mode="adaptive"` 下会被多个工作线程共享读写,但当前未做显式锁保护。
        # `NOTE:` 并发下的 `check-then-act` 可能导致重复工作(例如多次 `normalize`),但在 `CPython`+`GIL` 下通常不会导致崩溃。
        # `WARN:` `free-threaded`/`no-GIL` 的 `Python` 不在支持范围内;若要支持,必须为这些共享 `dict` 引入锁或线程安全容器。
        relation_cache = self.runtime.key_normalize_cache.get(self.relation_signature)
        if relation_cache is None:
            relation_cache = {}
            self.runtime.key_normalize_cache[self.relation_signature] = relation_cache

        fields_cache = relation_cache.get(from_fields)
        if fields_cache is None:
            fields_cache = {}
            relation_cache[from_fields] = fields_cache

        cached = fields_cache.get(row_id, MISSING)
        if cached is not MISSING:
            return cached

        self.maybe_warn_float_lookup_key(row_id, raw_key, step)
        normalized, status, error_message = self.runtime.normalize_lookup_key_with_status(raw_key, step)
        if status == "ok":
            fields_cache[row_id] = normalized
            return normalized
        lookup_result = "null_key" if status == "null_key" else "type_error"
        self.record_lookup(row_id, raw_key, normalized, step.to_source, lookup_result, error_message)
        fields_cache[row_id] = None
        return None

    def build_batch_rows(self) -> List[RowData]:
        field_keys = sorted(self.context.get_field_keys())
        return [build_row(self.context, row_id, field_keys) for row_id in self.batch_row_nth]


__all__ = ("LoadRefExecutionContext",)
