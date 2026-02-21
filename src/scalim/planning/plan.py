# region imports

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..planning.operators import PlanOperatorIr
from ..spec.ir.fields import SupportedFieldIr

if TYPE_CHECKING:
    from ..spec.ir.sources import SourceIr

# endregion


@dataclass
class Stage:
    """
    执行阶段: 将可并行执行的字段分组到同一阶段, 通常每个阶段包含一个或多个字段, 并且这些字段之间没有依赖关系
    """

    stage_id: str
    """
    阶段 ID
    """

    field_keys: list[str] = field(default_factory=list)
    """
    该阶段包含的字段键名列表
    """

    level: int = 0
    """
    依赖层级 (0 表示无依赖)
    """


@dataclass
class PlanMetadata:
    """
    计划元数据: 用于可视化和监控的元数据信息.
    """

    total_fields: int = 0
    """
    总字段数
    """

    total_sources: int = 0
    """
    总数据源数
    """

    total_loaders: int = 0
    """
    总 loader 调用数
    """

    pruned_fields: int = 0
    """
    被剪枝的字段数
    """

    max_depth: int = 0
    """
    最大依赖深度
    """

    has_derived_fields: bool = False
    """
    是否有派生字段
    """

    has_ref_fields: bool = False
    """
    是否有关联字段
    """

    cached_sources: list[str] = field(default_factory=list)
    """
    预加载缓存的数据源名称列表 (FR003)
    """


@dataclass
class ExecutionPlan:
    """
    执行计划(物理执行计划): planning 核心算子序列 (计算 required fields 的执行编排).

    说明:
    - `PlanBuilder` 仅生成 `load` / `load_ref` / `compute` 三类核心算子。
    - 输出写入与释放等操作属于 execution pipeline 的编排职责,不由 `PlanBuilder` 生成。
    """

    operators: tuple[PlanOperatorIr, ...] = field(default_factory=tuple)
    """Planning 核心算子序列 (按执行顺序).

    仅包含 `load` / `load_ref` / `compute`.
    """

    primary_field: str | None = None
    """主键字段名 (从 DemandIr 预计算)"""

    key_fields: frozenset[str] = field(default_factory=frozenset)
    """关键字段 (PK + FK, 不可提前释放)"""

    preload_sources: "tuple[SourceIr, ...]" = field(default_factory=tuple)
    """预加载数据源 (FR003)"""

    field_order: list[str] = field(default_factory=list)
    """拓扑排序后的字段顺序,包含中间依赖字段.

    仅用于执行顺序,不代表最终输出字段顺序.
    如需输出字段列表,请结合 target_fields 或 resolve_required_fields.
    """

    loader_sequence: "list[tuple[SourceIr, list[str]]]" = field(default_factory=list)
    """普通 loader 调用序列 [(source, [field_keys])]"""

    ref_loader_sequence: "list[tuple[SourceIr, list[tuple[str, str | tuple[str, ...]]]]]" = field(default_factory=list)
    """关联 loader 调用序列 [(source, [(field_key, dep_ref_field_keys)])].

    说明:
    - `dep_ref_field_keys` 是计划阶段的“依赖字段键(用于排序)”信号, 来源于 lookup steps 的 `from_field`.
      这里仅保留那些也对应到 **另一个 ref 字段** 的 key, 以便映射到某个 ref loader 并推断 loader 依赖图.
    - 它与运行时传入 loader callable 的 `lookup_keys`(值集合)无关.

    Example:
        # field: region_name (source=regions)
        # steps: from_field="region_id" -> regions
        # 且 demand 里存在 region_id 这个 ref 字段(source=customers)
        # => dep_ref_field_keys == ("region_id",)
    """

    stages: list[Stage] = field(default_factory=list)
    """执行阶段列表-并行预留"""

    metadata: PlanMetadata = field(default_factory=PlanMetadata)
    """计划元数据"""

    field_specs: dict[str, SupportedFieldIr] = field(default_factory=dict)
    """字段规格映射 (field_key -> FieldSpec)"""

    target_fields: list[str] = field(default_factory=list)
    """目标字段列表"""

    field_dependencies: "dict[str, tuple[str, ...]]" = field(default_factory=dict)
    """字段依赖映射 (field_key -> (dep1, dep2, ...)), 基于主数据源方向推断"""

    def to_viz_graph_snapshot(
        self,
        *,
        schema_version: str = "vizgraph/v1",
        include_stage_nodes: bool = True,
        include_loader_nodes: bool = True,
        include_source_nodes: bool = True,
    ) -> dict[str, Any]:
        """生成 VizGraphSnapshot(用于可视化).

        Returns:
            包含 nodes/edges/meta 的字典结构
        """
        from .viz import build_viz_graph_snapshot  # noqa: PLC0415

        return build_viz_graph_snapshot(
            self,
            schema_version=schema_version,
            include_stage_nodes=include_stage_nodes,
            include_loader_nodes=include_loader_nodes,
            include_source_nodes=include_source_nodes,
        )


__all__ = [
    "ExecutionPlan",
    "PlanMetadata",
    "Stage",
]
