# region imports

import logging
from typing import Any, Dict, FrozenSet, Hashable, List, MutableMapping, Optional, Set, Tuple

from ...._internal.utils.converters import auto_str_normalize_key
from ....hooks import HookManager
from ....ob.hub import InstrumentationHub
from ....ob.manager import ObserverManager
from ....planning.operators import LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks import ISink
from ....spec.ir import LookupStepIr, MainSourceIr, SourceIr, SupportedFieldIr
from ....spec.ir.lookup_casts import LookupCastSpecIr, lookup_cast_id
from ....typedefs import KeyNormalizationMode, LoaderResultMapping, LookupKey, ParallelMode, RowData
from ....utils.relation_signature import LoadRefCacheKey, RelationSignature, build_relation_signature
from ....vendor.dataclassesx import dataclass
from ...guardrails import GuardrailsPolicy
from ...key_normalization import normalize_key_normalization, should_apply_str_key_normalization
from ...loader_retry import LoaderRetryPolicies
from ...runtime_bindings import RuntimeBindings
from ...workflow_cache_pool import WorkflowCachePool
from ._internal.relation_guardrails import maybe_enforce_relation_guardrails

# endregion

# 模块日志记录器
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadRefCacheEntry:
    result: LoaderResultMapping
    batch_rows: Optional[List[RowData]] = None


class ExecutionRuntime:
    """执行运行时 - 共享资源"""

    preloaded_cache: MutableMapping[str, LoaderResultMapping]
    workflow_cache_pool: Optional[WorkflowCachePool]
    workflow_node_id: Optional[str]
    _preload_source_ids: FrozenSet[str]
    _preloaded_cache_str_views: Dict[str, LoaderResultMapping]
    load_ref_cache: Dict[LoadRefCacheKey, LoadRefCacheEntry]
    key_normalize_cache: Dict[RelationSignature, Dict[Tuple[Hashable, Tuple[str, ...]], Optional[LookupKey]]]
    load_ref_group_fields: Dict[RelationSignature, Tuple[str, ...]]
    load_ref_group_executed: Set[RelationSignature]
    rows_cache_logged: Set[RelationSignature]
    guardrail_logged: Set[Tuple[str, ...]]
    key_space_mismatch_logged: Set[Tuple[RelationSignature, str]]
    relation_guardrail_stats: Dict[int, Any]
    hook_manager: HookManager
    observer_manager: ObserverManager
    instrumentation: InstrumentationHub
    guardrails: GuardrailsPolicy
    loader_retry: LoaderRetryPolicies
    field_specs: Dict[str, SupportedFieldIr]
    sources: Dict[str, SourceIr]
    key_fields: FrozenSet[str]
    reverse_deps: Dict[str, Set[str]]
    field_consumers: Dict[str, int]
    target_fields: List[str]
    primary_field: Optional[str]
    main_source: Optional[MainSourceIr]
    sink: Optional[ISink]
    batch_num: int
    parallel_mode: ParallelMode
    max_workers: int
    key_normalization: KeyNormalizationMode
    adaptive_backend: Optional[str]
    adaptive_process_failure_mode: Optional[str]
    runtime_bindings: RuntimeBindings

    def __init__(
        self,
        plan: ExecutionPlan,
        hook_manager: HookManager,
        observer_manager: ObserverManager,
        main_source: Optional[MainSourceIr],
        sources: Dict[str, SourceIr],
        runtime_bindings: RuntimeBindings,
        guardrails: Optional[GuardrailsPolicy] = None,
        loader_retry: Optional[LoaderRetryPolicies] = None,
        *,
        parallel_mode: ParallelMode = "seq",
        max_workers: int = 0,
        key_normalization: KeyNormalizationMode = "raw",
        preloaded_cache: Optional[MutableMapping[str, LoaderResultMapping]] = None,
        workflow_cache_pool: Optional[WorkflowCachePool] = None,
        workflow_node_id: Optional[str] = None,
    ) -> None:
        self.preloaded_cache = preloaded_cache if preloaded_cache is not None else {}
        self._preloaded_cache_str_views = {}
        self.workflow_cache_pool = workflow_cache_pool
        self.workflow_node_id = str(workflow_node_id) if workflow_node_id is not None else None
        self.load_ref_cache = {}
        self.key_normalize_cache = {}
        self.hook_manager = hook_manager
        self.observer_manager = observer_manager
        self.instrumentation = InstrumentationHub(hook_manager=self.hook_manager, observer_manager=self.observer_manager)
        self.guardrails = guardrails or GuardrailsPolicy.disabled()
        self.loader_retry = loader_retry or LoaderRetryPolicies.disabled()
        self.runtime_bindings = runtime_bindings
        self.field_specs = plan.field_specs
        self.sources = dict(sources)
        self.key_fields = plan.key_fields
        self.target_fields = plan.target_fields
        self.primary_field = plan.primary_field
        self.main_source = main_source
        self.sink = None
        self.batch_num = 0
        self.parallel_mode = parallel_mode
        self.max_workers = max_workers
        self.key_normalization = normalize_key_normalization(key_normalization)
        self.adaptive_backend = None
        self.adaptive_process_failure_mode = None
        self._preload_source_ids = frozenset(str(source.source_id) for source in plan.preload_sources if source.is_preload_forever())

        self.reverse_deps = self._compute_reverse_deps(plan)
        self.field_consumers = self._compute_field_consumers()
        self.load_ref_group_fields = self._build_load_ref_group_fields(plan)
        self.load_ref_group_executed = set()
        self.rows_cache_logged = set()
        self.guardrail_logged = set()
        self.key_space_mismatch_logged = set()
        self.relation_guardrail_stats = {}

    def get_cached_source_mapping(self, step: LookupStepIr) -> LoaderResultMapping:
        source_id = str(step.to_source.source_id)
        mapping = self.preloaded_cache.get(source_id)
        if mapping is None:
            msg = "Unknown cached source '{}'".format(source_id)
            raise KeyError(msg)

        has_explicit_cast = step.lookup_cast is not None or step.to_source.key.cast is not None
        if not should_apply_str_key_normalization(self.key_normalization, has_explicit_cast=has_explicit_cast):
            return mapping

        cached_view = self._preloaded_cache_str_views.get(source_id)
        if cached_view is not None:
            return cached_view

        # 延迟构建规范化视图(稳定字符串 `key` 空间)用于匹配.
        out: Dict[LookupKey, object] = {}
        merged_collision_count = 0
        for raw_key, value in mapping.items():
            normalized_key, status, _error_message = auto_str_normalize_key(raw_key)
            if status != "ok" or normalized_key is None:
                continue
            if normalized_key in out:
                existing_value = out[normalized_key]
                same_value = False
                try:
                    same_value = existing_value == value
                except Exception:  # noqa: BLE001
                    same_value = False

                if same_value:
                    merged_collision_count += 1
                    continue

                msg = (
                    "key_normalization collision in cached source '{}' (mode='{}'): "
                    "multiple keys normalize to the same stable string key but values differ; fail-fast. "
                    "(redacted: raw keys omitted)"
                ).format(source_id, self.key_normalization)
                raise ValueError(msg)

            out[normalized_key] = value

        if merged_collision_count:
            self.instrumentation.emit_diagnostic_warning(
                message=(
                    "key_normalization collision in cached source '{}' (mode='{}'): "
                    "merged {} duplicate keys because values are equal. "
                    "Consider normalizing loader/cached mapping keys into a single key space. "
                    "(redacted: raw keys omitted)"
                ).format(source_id, self.key_normalization, merged_collision_count),
                source_id=source_id,
                field_id="(cache)",
                lookup_key=None,
                row_id="(cache)",
            )

        self._preloaded_cache_str_views[source_id] = out
        return out

    def _compute_reverse_deps(self, plan: ExecutionPlan) -> Dict[str, Set[str]]:
        """计算反向依赖"""
        reverse_deps: Dict[str, Set[str]] = {}
        for field_key in plan.field_specs:
            deps = plan.field_dependencies.get(field_key, ())
            for dep in deps:
                if dep not in reverse_deps:
                    reverse_deps[dep] = set()
                reverse_deps[dep].add(field_key)
        return reverse_deps

    def _compute_field_consumers(self) -> Dict[str, int]:
        """计算字段消费者数量"""
        field_consumers: Dict[str, int] = {}
        for field_key, dependents in self.reverse_deps.items():
            field_consumers[field_key] = len(dependents)
        return field_consumers

    def _build_load_ref_group_fields(
        self,
        plan: ExecutionPlan,
    ) -> Dict[RelationSignature, Tuple[str, ...]]:
        groups: Dict[RelationSignature, Set[str]] = {}
        for operator in plan.operators:
            if not isinstance(operator, LoadRefOperatorIr):
                continue
            relation_key = build_relation_signature(operator.lookup_steps)
            groups.setdefault(relation_key, set()).add(operator.field_key)
        return {key: tuple(sorted(fields)) for key, fields in groups.items()}

    def reset_load_ref_cache(self) -> None:
        """重置批次级缓存,在每次批次执行时释放内存占用."""
        if self.load_ref_cache:
            _logger.info(
                "`LoadRef` 批次缓存已清空: %d 条(批次=%s)",
                len(self.load_ref_cache),
                self.batch_num,
            )
        self.load_ref_cache = {}
        self.key_normalize_cache = {}
        self.load_ref_group_executed.clear()
        self.rows_cache_logged.clear()
        self.guardrail_logged.clear()
        self.relation_guardrail_stats.clear()

    def is_source_cached(self, source_name: str) -> bool:
        return source_name in self.preloaded_cache

    def get_from_cache(self, source_name: str, lookup_key: LookupKey) -> Optional[object]:
        cache = self.preloaded_cache.get(source_name)
        if cache is None:
            return None
        return cache.get(lookup_key)

    def normalize_lookup_key_with_status(
        self,
        raw_key: object,
        step: LookupStepIr,
    ) -> Tuple[Optional[LookupKey], str, Optional[str]]:
        """将外键值规范化为目标源键类型,并返回状态信息"""
        normalized, status, error_message = self._normalize_lookup_key_status(raw_key, step)
        maybe_enforce_relation_guardrails(self, step, status=status, error_message=error_message)
        return normalized, status, error_message

    def _normalize_lookup_key_status(
        self,
        raw_key: object,
        step: LookupStepIr,
    ) -> Tuple[Optional[LookupKey], str, Optional[str]]:
        if raw_key is None:
            return None, "null_key", None

        has_explicit_cast = step.lookup_cast is not None or step.to_source.key.cast is not None

        if step.lookup_cast is not None:
            candidate, status, error_message = self._apply_lookup_cast(
                step.lookup_cast,
                raw_key,
                is_multi=step.is_multi_field(),
                none_message="lookup_cast returned None",
            )
        elif step.to_source.key.cast is not None:
            candidate, status, error_message = self._apply_lookup_cast(
                step.to_source.key.cast,
                raw_key,
                is_multi=step.is_multi_field(),
                none_message="key.cast returned None",
            )
        else:
            candidate, status, error_message = raw_key, "ok", None

        if status != "ok" or candidate is None:
            return candidate, status, error_message

        if not should_apply_str_key_normalization(self.key_normalization, has_explicit_cast=has_explicit_cast):
            return candidate, "ok", None

        normalized_key, norm_status, norm_error_message = auto_str_normalize_key(candidate)
        if norm_status != "ok":
            return None, norm_status, norm_error_message
        return normalized_key, "ok", None

    def _apply_lookup_cast(
        self,
        lookup_cast: LookupCastSpecIr,
        raw_key: object,
        *,
        is_multi: bool,
        none_message: str,
    ) -> Tuple[Optional[LookupKey], str, Optional[str]]:
        cast_fn = self.runtime_bindings.get_lookup_key_cast(lookup_cast_id(lookup_cast, is_multi=is_multi))
        if cast_fn is None:
            msg = "Missing runtime lookup_cast callable for {}".format(lookup_cast_id(lookup_cast, is_multi=is_multi))
            raise KeyError(msg)
        try:
            normalized = cast_fn(raw_key)
        except (ValueError, TypeError) as exc:
            return None, "type_error", str(exc)

        if normalized is None:
            return None, "type_error", none_message

        return normalized, "ok", None

    def normalize_lookup_key(
        self,
        raw_key: object,
        step: LookupStepIr,
    ) -> Optional[LookupKey]:
        """将外键值规范化为目标源键类型"""
        normalized, status, _ = self.normalize_lookup_key_with_status(raw_key, step)
        if status != "ok":
            return None
        return normalized


__all__ = ()
