# region imports

import logging
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Hashable, List, MutableMapping, Optional, Set, Tuple

from ....hooks.base import HookManager
from ....ob.hub import InstrumentationHub
from ....ob.manager import ObserverManager
from ....planning.operators import LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks.sink_base import ISink
from ....spec.ir.aliases import LookupKeyCast
from ....spec.ir.fields import SupportedFieldIr
from ....spec.ir.relations import LookupStepIr
from ....spec.ir.sources import MainSourceIr
from ....typedefs import LoaderResultMapping, LookupKey, ParallelMode, RowData
from ...guardrails import GuardrailsPolicy
from ...loader_retry import LoaderRetryPolicies
from ..helpers.relation_signature import LoadRefCacheKey, RelationSignature, build_relation_signature
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
    _preload_source_ids: FrozenSet[str]
    load_ref_cache: Dict[LoadRefCacheKey, LoadRefCacheEntry]
    key_normalize_cache: Dict[RelationSignature, Dict[Tuple[Hashable, Tuple[str, ...]], Optional[LookupKey]]]
    load_ref_group_fields: Dict[RelationSignature, Tuple[str, ...]]
    load_ref_group_executed: Set[RelationSignature]
    rows_cache_logged: Set[RelationSignature]
    guardrail_logged: Set[Tuple[str, ...]]
    relation_guardrail_stats: Dict[int, Any]
    hook_manager: HookManager
    observer_manager: ObserverManager
    instrumentation: InstrumentationHub
    guardrails: GuardrailsPolicy
    loader_retry: LoaderRetryPolicies
    field_specs: Dict[str, SupportedFieldIr]
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
    adaptive_backend: Optional[str]
    adaptive_process_failure_mode: Optional[str]

    def __init__(
        self,
        plan: ExecutionPlan,
        hook_manager: HookManager,
        observer_manager: ObserverManager,
        main_source: Optional[MainSourceIr],
        guardrails: Optional[GuardrailsPolicy] = None,
        loader_retry: Optional[LoaderRetryPolicies] = None,
        *,
        parallel_mode: ParallelMode = "seq",
        max_workers: int = 0,
        preloaded_cache: Optional[MutableMapping[str, LoaderResultMapping]] = None,
    ) -> None:
        self.preloaded_cache = preloaded_cache if preloaded_cache is not None else {}
        self.load_ref_cache = {}
        self.key_normalize_cache = {}
        self.hook_manager = hook_manager
        self.observer_manager = observer_manager
        self.instrumentation = InstrumentationHub(hook_manager=self.hook_manager, observer_manager=self.observer_manager)
        self.guardrails = guardrails or GuardrailsPolicy.disabled()
        self.loader_retry = loader_retry or LoaderRetryPolicies.disabled()
        self.field_specs = plan.field_specs
        self.key_fields = plan.key_fields
        self.target_fields = plan.target_fields
        self.primary_field = plan.primary_field
        self.main_source = main_source
        self.sink = None
        self.batch_num = 0
        self.parallel_mode = parallel_mode
        self.max_workers = max_workers
        self.adaptive_backend = None
        self.adaptive_process_failure_mode = None
        self._preload_source_ids = frozenset(str(source.source_id) for source in plan.preload_sources if source.is_preload_forever())

        self.reverse_deps = self._compute_reverse_deps(plan)
        self.field_consumers = self._compute_field_consumers()
        self.load_ref_group_fields = self._build_load_ref_group_fields(plan)
        self.load_ref_group_executed = set()
        self.rows_cache_logged = set()
        self.guardrail_logged = set()
        self.relation_guardrail_stats = {}

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

        if step.lookup_cast is not None:
            return self._apply_lookup_cast(step.lookup_cast, raw_key, none_message="lookup_cast returned None")

        if step.to_source.key.cast is not None:
            return self._apply_lookup_cast(step.to_source.key.cast, raw_key, none_message="key.cast returned None")

        return raw_key, "ok", None

    def _apply_lookup_cast(
        self,
        lookup_cast: LookupKeyCast,
        raw_key: object,
        *,
        none_message: str,
    ) -> Tuple[Optional[LookupKey], str, Optional[str]]:
        try:
            normalized = lookup_cast(raw_key)
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
