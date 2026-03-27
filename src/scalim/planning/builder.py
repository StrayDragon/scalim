# region imports

from typing import Dict, List, Optional, Set, Tuple

from .._internal.utils import graph
from ..spec.ir import DemandIr, DerivedFieldIr, FieldIr, SourceIr
from .builder_helpers.dep_graph import build_dependency_graph, build_field_dependencies
from .builder_helpers.key_fields import compute_key_fields
from .builder_helpers.operators import (
    build_plan_operators,
    derive_pre_ref_available_field_keys,
    derive_pre_ref_derived_field_keys,
)
from .builder_helpers.resolver import LookupStepsResolver, extract_relation_dependency_keys
from .loader_ordering.sequences import build_loader_sequences
from .metadata import build_metadata
from .plan import ExecutionPlan
from .stages import build_stages

# endregion


class PlanBuilder:
    """
    执行计划构建器.

    链路:`demand` -> `ExecutionPlan`.


    1. 单级单字段关联:
    `orders.customer_id` -> `customers.customer_id`
    依赖: [`customer_id`]

    2. 单级多字段关联 (复合键):
    `orders.(region_id, institution_id)` -> `mapping.(region_id, institution_id)`
    依赖: [`region_id`, `institution_id`]

    3. 多级关联:
    `orders.pay_id` -> `pays.pay_id` -> `pays.country_id` -> `countries.country_id`
    依赖: [`pay_id`, `country_id`]  # 包含所有中间路径的字段
    """

    demand: DemandIr
    _resolver: LookupStepsResolver
    _graph: "graph.DependencyGraph[str]"

    def __init__(self, demand: DemandIr) -> None:
        self.demand = demand
        self._resolver = LookupStepsResolver()
        self._graph = build_dependency_graph(demand=self.demand, resolver=self._resolver)

    def build(self, targets: Optional[List[str]] = None) -> ExecutionPlan:
        """构建执行计划"""
        if targets is None:
            targets = list(self.demand.fields.keys())

        for target in targets:
            if target not in self.demand.fields:
                msg = f"目标字段 {target!r} 不存在"
                raise ValueError(msg)

        required_fields = self._collect_dependencies(targets)

        cycles = self._graph.detect_cycles()
        if cycles:
            cycle = cycles[0] if cycles else []
            cycle_path = " -> ".join(str(x) for x in cycle) if cycle else str(cycles)
            msg = "检测到循环依赖: {}".format(cycle_path)

            has_derived = any(isinstance(self.demand.fields.get(str(x)), DerivedFieldIr) for x in cycle)
            has_ref = False
            for node_id in cycle:
                field = self.demand.fields.get(str(node_id))
                if isinstance(field, FieldIr) and (field.lookup_steps or field.relation):
                    has_ref = True
                    break
            if has_derived and has_ref:
                msg = (
                    msg
                    + "\nHint: this may be caused by derived fields participating in relation join keys while "
                    + "depending (directly/indirectly) on ref fields. "
                    + "Only pre-relation derived fields (depending only on main_source non-ref fields) are allowed."
                )

            raise graph.ScalimCyclicDependencyError(msg, cycles)

        field_order = graph.topological_sort(required_fields, self._graph.get_deps)
        pre_ref_available = derive_pre_ref_available_field_keys(demand=self.demand)
        pre_ref_derived = derive_pre_ref_derived_field_keys(
            demand=self.demand,
            field_order=field_order,
            pre_ref_available=pre_ref_available,
        )
        self._validate_relation_from_derived_fields(
            required_fields=required_fields,
            pre_ref_available=pre_ref_available,
            pre_ref_derived=pre_ref_derived,
        )
        loader_sequence, ref_loader_sequence = build_loader_sequences(self.demand, required_fields)
        stages = build_stages(field_order, self._graph.get_deps)
        field_specs = {key: self.demand.fields[key] for key in field_order if key in self.demand.fields}
        max_depth = stages[-1].level if stages else 0
        metadata = build_metadata(
            demand=self.demand,
            required_fields=required_fields,
            loader_sequence=loader_sequence,
            ref_loader_sequence=ref_loader_sequence,
            max_depth=max_depth,
        )

        operators = build_plan_operators(
            demand=self.demand,
            resolver=self._resolver,
            required_fields=required_fields,
            field_order=field_order,
            loader_sequence=loader_sequence,
            ref_loader_sequence=ref_loader_sequence,
            pre_ref_derived=pre_ref_derived,
        )

        primary_field = self._get_primary_field_key()

        key_fields = compute_key_fields(demand=self.demand, resolver=self._resolver, required_fields=required_fields)

        preload_sources = self._collect_preload_sources()

        # 构建字段依赖映射(基于主数据源方向推断)
        field_dependencies = build_field_dependencies(field_order=field_order, dep_graph=self._graph)

        return ExecutionPlan(
            operators=operators,
            primary_field=primary_field,
            key_fields=key_fields,
            preload_sources=preload_sources,
            field_order=field_order,
            loader_sequence=loader_sequence,
            ref_loader_sequence=ref_loader_sequence,
            stages=stages,
            metadata=metadata,
            field_specs=field_specs,
            target_fields=targets,
            field_dependencies=field_dependencies,
        )

    def _validate_relation_from_derived_fields(
        self,
        *,
        required_fields: Set[str],
        pre_ref_available: Set[str],
        pre_ref_derived: Set[str],
    ) -> None:
        """校验当 `relation` 的连接键引用派生字段时,其满足 `pre-ref` 约束."""

        derived_consumers: Dict[str, Set[str]] = {}
        for field_key in required_fields:
            field_spec = self.demand.fields.get(field_key)
            if not isinstance(field_spec, FieldIr):
                continue
            if not (field_spec.lookup_steps or field_spec.relation):
                continue

            deps = extract_relation_dependency_keys(
                demand=self.demand,
                field_spec=field_spec,
                resolver=self._resolver,
                field_key=str(field_key),
            )
            for dep_key in deps:
                dep_spec = self.demand.fields.get(dep_key)
                if isinstance(dep_spec, DerivedFieldIr):
                    derived_consumers.setdefault(str(dep_key), set()).add(str(field_key))

        if not derived_consumers:
            return

        for derived_key in sorted(derived_consumers.keys()):
            if derived_key in pre_ref_derived:
                continue

            chain = self._find_pre_ref_blocking_chain(
                start=str(derived_key),
                pre_ref_available=pre_ref_available,
                pre_ref_derived=pre_ref_derived,
            )
            consumers = ",".join(sorted(derived_consumers.get(str(derived_key), set())))
            chain_text = " -> ".join(chain) if chain else str(derived_key)
            msg = (
                "Derived field {!r} is used as relation join key (consumed_by={}), "
                "but it is not pre-relation computable. "
                "Blocking dependency chain: {}"
            ).format(str(derived_key), consumers, chain_text)
            raise ValueError(msg)

    def _find_pre_ref_blocking_chain(
        self,
        *,
        start: str,
        pre_ref_available: Set[str],
        pre_ref_derived: Set[str],
    ) -> List[str]:
        """返回一个阻塞链条: 起点 -> ... -> 阻塞节点."""

        seen: Set[str] = set()
        stack: List[Tuple[str, List[str]]] = [(str(start), [str(start)])]

        while stack:
            current, path = stack.pop()
            if current in seen:
                continue
            seen.add(current)

            field_spec = self.demand.fields.get(current)
            if not isinstance(field_spec, DerivedFieldIr):
                return path

            deps = tuple(field_spec.dependencies or ())
            if not deps:
                return path

            for dep in deps:
                if dep in pre_ref_available or dep in pre_ref_derived:
                    continue
                dep_spec = self.demand.fields.get(dep)
                if dep_spec is None:
                    return [*path, str(dep)]
                if isinstance(dep_spec, FieldIr):
                    return [*path, str(dep)]
                if isinstance(dep_spec, DerivedFieldIr):
                    stack.append((str(dep), [*path, str(dep)]))
                    continue
                return [*path, str(dep)]

        return [str(start)]

    def _get_primary_field_key(self) -> Optional[str]:
        """获取主键字段名"""
        primary_field = self.demand.get_primary_field()
        return primary_field.field_id if primary_field else None

    def _collect_preload_sources(self) -> Tuple[SourceIr, ...]:
        """收集预加载数据源 (FR003)"""
        preload_sources: List[SourceIr] = []
        for source in self.demand.sources.values():
            if source.is_preload_forever():
                preload_sources.append(source)
        return tuple(preload_sources)

    def _collect_dependencies(self, targets: List[str]) -> Set[str]:
        def get_deps_with_fk(field_key: str) -> List[str]:
            if field_key not in self.demand.fields:
                return []
            return self._graph.get_deps(field_key)

        return graph.collect_dependencies(targets, get_deps_with_fk)


__all__ = []
