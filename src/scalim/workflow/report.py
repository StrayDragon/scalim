"""`workflow` 运行结果与错误结构.

说明:
- 本模块不承载执行逻辑,仅承载结果/错误数据结构,便于在重构中保持稳定边界.
- 为保持 `scalim.workflow` 不依赖 `scalim.dsl`,`WorkflowRunOutcome.result` 使用 `object` 承载由上层适配层组装的结果对象.
- 运行时需兼容 `Python 3.6`.
"""

from typing import List, Optional, Tuple

from ..vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class WorkflowRunError:
    run_id: str
    demand_path: str
    exc_type: str
    message: str
    diff: Optional[List[str]] = None


@dataclass(frozen=True)
class WorkflowRunOutcome:
    run_id: str
    demand_path: str
    result: Optional[object] = None
    error: Optional[WorkflowRunError] = None


@dataclass(frozen=True)
class WorkflowResult:
    outcomes: Tuple[WorkflowRunOutcome, ...]

    def errors(self) -> List[WorkflowRunError]:
        rows: List[WorkflowRunError] = []
        for item in self.outcomes:
            if item.error is not None:
                rows.append(item.error)
        return rows


__all__ = (
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunOutcome",
)
