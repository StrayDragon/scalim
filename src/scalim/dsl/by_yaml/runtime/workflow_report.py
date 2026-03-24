"""`workflow` 运行结果与错误结构.

说明:
- 该模块不承载执行逻辑,仅承载结果/错误数据结构,便于在重构中保持稳定边界
- 运行时需兼容 `Python 3.6`
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .contracts import RunResult


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
    result: Optional[RunResult] = None
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


__all__ = [
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunOutcome",
]
