# region imports

import logging
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

from ....hooks.base import HookManager
from ....ob.hub import InstrumentationHub
from ....ob.manager import ObserverManager
from ....planning.operators import LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....sinks.sink_base import ISink
from ....spec.ir.fields import SupportedFieldIr
from ....spec.ir.relations import LookupStepIr
from ....spec.ir.sources import MainSourceIr
from ....typedefs import ParallelMode, RowData
from ...guardrails import GuardrailsPolicy
from ...loader_retry import LoaderRetryPolicies
from ..helpers.relation_signature import build_relation_signature
from ._internal.relation_guardrails import maybe_enforce_relation_guardrails

# endregion

# module logger
_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadRefCacheEntry:
    result: dict[Hashable, Any]
    batch_rows: list[RowData] | None = None


class ExecutionRuntime:
    """执行运行时 - 共享资源"""

    preloaded_cache: dict[str, dict[Hashable, Any]]
    load_ref_cache: dict[tuple[Any, ...], LoadRefCacheEntry]
    key_normalize_cache: dict[tuple[tuple[Any, ...], ...], dict[tuple[Hashable, tuple[str, ...]], Hashable | None]]
    load_ref_group_fields: dict[tuple[tuple[Any, ...], ...], tuple[str, ...]]
    load_ref_group_executed: set[tuple[tuple[Any, ...], ...]]
    rows_cache_logged: set[tuple[tuple[Any, ...], ...]]
    guardrail_logged: set[tuple[str, ...]]
    relation_guardrail_stats: dict[int, Any]
    hook_manager: HookManager
    observer_manager: ObserverManager
    instrumentation: InstrumentationHub
    guardrails: GuardrailsPolicy
    loader_retry: LoaderRetryPolicies
    field_specs: dict[str, SupportedFieldIr]
    key_fields: frozenset[str]
    reverse_deps: dict[str, set[str]]
    field_consumers: dict[str, int]
    target_fields: list[str]
    primary_field: str | None
    main_source: MainSourceIr | None
    sink: ISink | None
    batch_num: int
    parallel_mode: ParallelMode
    max_workers: int

    def __init__(
        self,
        plan: ExecutionPlan,
        hook_manager: HookManager,
        observer_manager: ObserverManager,
        main_source: MainSourceIr | None,
        guardrails: GuardrailsPolicy | None = None,
        loader_retry: LoaderRetryPolicies | None = None,
        *,
        parallel_mode: ParallelMode = "seq",
        max_workers: int = 0,
    ) -> None:
        self.preloaded_cache = {}
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

        self.reverse_deps = self._compute_reverse_deps(plan)
        self.field_consumers = self._compute_field_consumers()
        self.load_ref_group_fields = self._build_load_ref_group_fields(plan)
        self.load_ref_group_executed = set()
        self.rows_cache_logged = set()
        self.guardrail_logged = set()
        self.relation_guardrail_stats = {}

    def _compute_reverse_deps(self, plan: ExecutionPlan) -> dict[str, set[str]]:
        """计算反向依赖"""
        reverse_deps: dict[str, set[str]] = {}
        for field_key in plan.field_specs:
            deps = plan.field_dependencies.get(field_key, ())
            for dep in deps:
                if dep not in reverse_deps:
                    reverse_deps[dep] = set()
                reverse_deps[dep].add(field_key)
        return reverse_deps

    def _compute_field_consumers(self) -> dict[str, int]:
        """计算字段消费者数量"""
        field_consumers: dict[str, int] = {}
        for field_key, dependents in self.reverse_deps.items():
            field_consumers[field_key] = len(dependents)
        return field_consumers

    def _build_load_ref_group_fields(
        self,
        plan: ExecutionPlan,
    ) -> dict[tuple[tuple[Any, ...], ...], tuple[str, ...]]:
        groups: dict[tuple[tuple[Any, ...], ...], set[str]] = {}
        for operator in plan.operators:
            if not isinstance(operator, LoadRefOperatorIr):
                continue
            relation_key = build_relation_signature(operator.lookup_steps)
            groups.setdefault(relation_key, set()).add(operator.field_key)
        return {key: tuple(sorted(fields)) for key, fields in groups.items()}

    def reset_load_ref_cache(self) -> None:
        """重置批次级缓存,在每次 batch 执行时释放内存占用."""
        if self.load_ref_cache:
            _logger.info(
                "LoadRef batch cache cleared: %d entries (batch=%s)",
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

    def get_from_cache(self, source_name: str, lookup_key: Any) -> Any | None:
        cache = self.preloaded_cache.get(source_name)
        if cache is None:
            return None
        return cache.get(lookup_key)

    def normalize_lookup_key_with_status(
        self,
        raw_key: Any,
        step: LookupStepIr,
    ) -> tuple[Hashable | None, str, str | None]:
        """将外键值规范化为目标源 key 类型,并返回状态信息"""
        normalized, status, error_message = self._normalize_lookup_key_status(raw_key, step)
        maybe_enforce_relation_guardrails(self, step, status=status, error_message=error_message)
        return normalized, status, error_message

    def _normalize_lookup_key_status(
        self,
        raw_key: Any,
        step: LookupStepIr,
    ) -> tuple[Hashable | None, str, str | None]:
        if raw_key is None:
            return None, "null_key", None

        if step.lookup_cast is not None:
            return self._apply_lookup_cast(step.lookup_cast, raw_key, none_message="lookup_cast returned None")

        if step.to_source.key.cast is not None:
            return self._apply_lookup_cast(step.to_source.key.cast, raw_key, none_message="key.cast returned None")

        return raw_key, "ok", None

    def _apply_lookup_cast(
        self,
        lookup_cast: Any,
        raw_key: Any,
        *,
        none_message: str,
    ) -> tuple[Hashable | None, str, str | None]:
        try:
            normalized = lookup_cast(raw_key)
        except (ValueError, TypeError) as exc:
            return None, "type_error", str(exc)

        if normalized is None:
            return None, "type_error", none_message

        return normalized, "ok", None

    def normalize_lookup_key(
        self,
        raw_key: Any,
        step: LookupStepIr,
    ) -> Hashable | None:
        """将外键值规范化为目标源 key 类型"""
        normalized, status, _ = self.normalize_lookup_key_with_status(raw_key, step)
        if status != "ok":
            return None
        return normalized
