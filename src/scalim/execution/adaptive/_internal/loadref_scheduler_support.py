import os
from dataclasses import dataclass
from typing import Callable, Dict, Hashable, List, MutableMapping, Optional, Sequence, Set, Tuple

from ....events.event import Event
from ....hooks.base import HookManager
from ....ob.manager import ObserverManager
from ....planning.operators import LoadRefOperatorIr
from ....planning.plan import ExecutionPlan
from ....spec.ir.sources import MainSourceIr
from ....typedefs import FieldValue, LoaderResultMapping
from ...context import BatchContext
from ...executor.operators.load_ref.executor import LoadRefOperatorExecutor
from ...executor.runtime.runtime import ExecutionRuntime
from ...guardrails import GuardrailsPolicy
from ...loader_retry import LoaderRetryPolicies
from ..capture import HookRecordedEvent
from ..overlay_context import OverlayBatchContext


def resolve_adaptive_max_workers(max_workers: int, cpu_count_fn: Optional[Callable[[], Optional[int]]] = None) -> int:
    if max_workers and max_workers > 0:
        return max(1, int(max_workers))
    resolver = cpu_count_fn or os.cpu_count
    cpu = resolver() or 1
    return max(1, min(32, cpu + 4))


@dataclass(frozen=True)
class AdaptiveTaskResult:
    overlay: Dict[str, Dict[Hashable, FieldValue]]
    hook_events: List[HookRecordedEvent]
    observer_events: List[Event]
    relation_key: Tuple[Tuple[object, ...], ...]
    group_enabled: bool


def run_task_in_process(
    plan: ExecutionPlan,
    op: LoadRefOperatorIr,
    relation_key: Tuple[Tuple[object, ...], ...],
    base_context: BatchContext,
    batch_row_nth: List[Hashable],
    main_source: Optional[MainSourceIr],
    guardrails: GuardrailsPolicy,
    loader_retry: LoaderRetryPolicies,
    preloaded_cache: MutableMapping[str, LoaderResultMapping],
    batch_num: int,
    required_fields: Optional[Set[str]],
    *,
    group_enabled: bool,
) -> AdaptiveTaskResult:
    task_runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(),
        main_source=main_source,
        guardrails=guardrails,
        loader_retry=loader_retry,
        parallel_mode="seq",
        max_workers=0,
    )
    task_runtime.preloaded_cache = preloaded_cache
    task_runtime.batch_num = int(batch_num)

    task_context = OverlayBatchContext(base_context, required_fields=required_fields)
    LoadRefOperatorExecutor().execute(op, task_context, batch_row_nth, task_runtime)

    overlay = task_context.drain_overlay()
    return AdaptiveTaskResult(
        overlay=overlay,
        hook_events=[],
        observer_events=[],
        relation_key=relation_key,
        group_enabled=bool(group_enabled),
    )


def build_ref_deps(plan: ExecutionPlan) -> Dict[str, Tuple[str, ...]]:
    deps: Dict[str, Tuple[str, ...]] = {}
    for _source, items in plan.ref_loader_sequence:
        for field_key, dep_ref_field_keys in items:
            deps[str(field_key)] = tuple(str(dep) for dep in (dep_ref_field_keys or ()))
    return deps


def build_layers(field_keys: Sequence[str], *, deps: Dict[str, Tuple[str, ...]]) -> List[List[str]]:
    remaining: Set[str] = set(field_keys)
    done: Set[str] = set()
    layers: List[List[str]] = []

    while remaining:
        ready: List[str] = []
        for key in field_keys:
            if key not in remaining:
                continue
            key_deps = deps.get(key, ())
            if all(dep in done or dep not in remaining for dep in key_deps):
                ready.append(key)

        if not ready:
            layers.append([key for key in field_keys if key in remaining])
            break

        layers.append(ready)
        for key in ready:
            remaining.remove(key)
            done.add(key)

    return layers
