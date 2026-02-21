# region imports


from ..spec.ir.demand import DemandIr
from ..spec.ir.sources import SourceIr
from ..utils import graph
from .builder_helpers.dep_graph import build_dependency_graph, build_field_dependencies
from .builder_helpers.key_fields import compute_key_fields
from .builder_helpers.operators import build_plan_operators
from .builder_helpers.resolver import LookupStepsResolver
from .loader_ordering.sequences import build_loader_sequences
from .metadata import build_metadata
from .plan import ExecutionPlan
from .stages import build_stages

# endregion


class PlanBuilder:
    """
    执行计划构建器

    plan: demand -> (execution) plan


    1. 单级单字段关联:
    orders.customer_id -> customers.customer_id
    依赖: [customer_id]

    2. 单级多字段关联 (复合键):
    orders.(region_id, institution_id) -> mapping.(region_id, institution_id)
    依赖: [region_id, institution_id]

    3. 多级关联:
    orders.pay_id -> pays.pay_id -> pays.country_id -> countries.country_id
    依赖: [pay_id, country_id]  # 包含所有中间路径的字段
    """

    demand: DemandIr
    _resolver: LookupStepsResolver
    _graph: "graph.DependencyGraph[str]"

    def __init__(self, demand: DemandIr) -> None:
        self.demand = demand
        self._resolver = LookupStepsResolver()
        self._graph = build_dependency_graph(demand=self.demand, resolver=self._resolver)

    def build(self, targets: list[str] | None = None) -> ExecutionPlan:
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
            msg = f"检测到循环依赖: {cycles}"
            raise graph.CyclicDependencyError(msg, cycles)

        field_order = graph.topological_sort(required_fields, self._graph.get_deps)
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

    def _get_primary_field_key(self) -> str | None:
        """获取主键字段名"""
        primary_field = self.demand.get_primary_field()
        return primary_field.field_id if primary_field else None

    def _collect_preload_sources(self) -> tuple[SourceIr, ...]:
        """收集预加载数据源 (FR003)"""
        preload_sources: list[SourceIr] = []
        for source in self.demand.sources.values():
            if source.is_preload_forever():
                preload_sources.append(source)
        return tuple(preload_sources)

    def _collect_dependencies(self, targets: list[str]) -> set[str]:
        def get_deps_with_fk(field_key: str) -> list[str]:
            if field_key not in self.demand.fields:
                return []
            return self._graph.get_deps(field_key)

        return graph.collect_dependencies(targets, get_deps_with_fk)
