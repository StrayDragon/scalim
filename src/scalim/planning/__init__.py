"""规划层入口.

此包提供规划层的稳定导入路径,供用户侧构建执行计划并做可视化/分析.
"""

# pragma: scalim-public-api tier1:80:scalim.planning|规划层入口|规划/编排/可视化分析

from .builder import PlanBuilder
from .operators import ComputeOperatorIr, LoadOperatorIr, LoadRefOperatorIr, OperatorType, PlanOperatorIr
from .plan import ComputeFusionGroup, ExecutionPlan, PlanMetadata, Stage

__all__ = (
    "ComputeFusionGroup",
    "ComputeOperatorIr",
    "ExecutionPlan",
    "LoadOperatorIr",
    "LoadRefOperatorIr",
    "OperatorType",
    "PlanBuilder",
    "PlanMetadata",
    "PlanOperatorIr",
    "Stage",
)
