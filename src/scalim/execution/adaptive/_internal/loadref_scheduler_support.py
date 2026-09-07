import os
import warnings
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

from ....events import Event
from ....planning.plan import ExecutionPlan
from ....typedefs import FieldValue
from ....utils.relation_signature import RelationSignature
from ..capture import HookRecordedEvent


def resolve_adaptive_max_workers(max_workers: int, cpu_count_fn: Callable[[], int | None] | None = None) -> int:
    resolver = cpu_count_fn or os.cpu_count
    cpu = resolver() or 1

    if max_workers and max_workers > 0:
        requested = max(1, int(max_workers))
        hard_cap = min(256, max(32, int(cpu) * 5))
        resolved = min(requested, hard_cap)
        if resolved < requested:
            warnings.warn(
                f"`adaptive` 模式 `max_workers` 被护栏裁剪: 请求={requested} 解析={resolved} 上限={hard_cap} `cpu_count`={cpu}",
                stacklevel=2,
            )
        return resolved
    return max(1, min(32, cpu + 4))


@dataclass(frozen=True)
class AdaptiveTaskResult:
    overlay: dict[str, dict[Hashable, FieldValue]]
    hook_events: list[HookRecordedEvent]
    observer_events: list[Event]
    relation_key: RelationSignature
    group_enabled: bool


def build_ref_deps(plan: ExecutionPlan) -> dict[str, tuple[str, ...]]:
    deps: dict[str, tuple[str, ...]] = {}
    for _source, items in plan.ref_loader_sequence:
        for field_key, dep_ref_field_keys in items:
            deps[str(field_key)] = tuple(str(dep) for dep in (dep_ref_field_keys or ()))
    return deps


def build_layers(field_keys: Sequence[str], *, deps: dict[str, tuple[str, ...]]) -> list[list[str]]:
    remaining: set[str] = set(field_keys)
    done: set[str] = set()
    layers: list[list[str]] = []

    while remaining:
        ready: list[str] = []
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


__all__ = ()
