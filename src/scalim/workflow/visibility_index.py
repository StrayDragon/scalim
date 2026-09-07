from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..spec.ir._workflow import WorkflowIr


def _validate_workflow_node_ids(*, deps_by_node_id: Mapping[str, Sequence[str]]) -> set[str]:
    node_ids: set[str] = set()
    for raw_node_id in deps_by_node_id:
        node_id = str(raw_node_id).strip()
        if not node_id:
            msg = "workflow node_id must be a non-empty string"
            raise ValueError(msg)
        if node_id in node_ids:
            msg = f"workflow node_id duplicated: {node_id!r}"
            raise ValueError(msg)
        node_ids.add(node_id)
    return node_ids


def _normalize_workflow_deps(*, deps_by_node_id: Mapping[str, Sequence[str]]) -> dict[str, tuple[str, ...]]:
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_node_id, deps in deps_by_node_id.items():
        consumer = str(raw_node_id).strip()
        if not consumer:
            msg = "workflow node_id must be a non-empty string"
            raise ValueError(msg)

        tmp: set[str] = set()
        for dep_id in deps or ():
            dep = str(dep_id).strip()
            if not dep:
                msg = f"workflow deps must contain only non-empty strings (node_id={consumer!r})"
                raise ValueError(msg)
            tmp.add(dep)
        normalized[consumer] = tuple(sorted(tmp))
    return normalized


def _validate_workflow_deps_exist(*, deps_by_node_id: Mapping[str, Sequence[str]], node_ids: set[str]) -> None:
    for raw_consumer, deps in deps_by_node_id.items():
        consumer = str(raw_consumer).strip()
        for raw_dep in deps or ():
            dep = str(raw_dep).strip()
            if dep and dep not in node_ids:
                msg = f"workflow node {consumer!r} depends_on unknown node {dep!r}"
                raise ValueError(msg)


def _build_workflow_visibility_closure(*, deps_by_node_id: Mapping[str, tuple[str, ...]], node_ids: set[str]) -> dict[str, frozenset[str]]:
    cache: dict[str, frozenset[str]] = {}
    visiting: set[str] = set()

    def _visible(consumer_node_id: str) -> frozenset[str]:
        cached = cache.get(consumer_node_id)
        if cached is not None:
            return cached

        if consumer_node_id in visiting:
            msg = f"workflow depends_on cycle detected at node_id={consumer_node_id!r}"
            raise ValueError(msg)

        visiting.add(consumer_node_id)
        out: set[str] = set()
        for dep in deps_by_node_id.get(consumer_node_id, ()):
            out.add(dep)
            out.update(_visible(dep))
        visiting.remove(consumer_node_id)

        frozen = frozenset(out)
        cache[consumer_node_id] = frozen
        return frozen

    return {node_id: _visible(node_id) for node_id in sorted(node_ids)}


@dataclass(frozen=True)
class WorkflowVisibilityIndex:
    """`workflow` 节点可见性闭包(`SSOT`).

    可见性规则:
    - 对于 `consumer` 节点,其可见 `producer` 集合为 `depends_on` 的传递闭包(不包含自身).
    - 该对象仅做纯计算/纯数据,用于在上下文引用与产物读取等处复用.
    """

    visible_by_consumer_node_id: dict[str, frozenset[str]]

    @classmethod
    def build(cls, *, deps_by_node_id: Mapping[str, Sequence[str]]) -> "WorkflowVisibilityIndex":
        node_ids = _validate_workflow_node_ids(deps_by_node_id=deps_by_node_id)
        _validate_workflow_deps_exist(deps_by_node_id=deps_by_node_id, node_ids=node_ids)
        normalized_deps = _normalize_workflow_deps(deps_by_node_id=deps_by_node_id)
        visible_by_consumer = _build_workflow_visibility_closure(deps_by_node_id=normalized_deps, node_ids=node_ids)
        return cls(visible_by_consumer_node_id=visible_by_consumer)

    @classmethod
    def from_workflow_ir(cls, workflow_ir: WorkflowIr) -> "WorkflowVisibilityIndex":
        deps_by_node_id = {str(node.node_id): tuple(str(dep_id) for dep_id in node.deps) for node in workflow_ir.nodes}
        return cls.build(deps_by_node_id=deps_by_node_id)

    def visible_producer_node_ids(self, consumer_node_id: str) -> frozenset[str]:
        return self.visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())


__all__ = ()
