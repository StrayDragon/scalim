from abc import ABC, abstractmethod
from typing import Hashable, List

from ....planning.operators import SupportedOperatorIr
from ...context import BatchContext
from ..runtime.runtime import ExecutionRuntime


class OperatorExecutor(ABC):
    """算子执行器基类"""

    @abstractmethod
    def execute(
        self,
        operator: SupportedOperatorIr,
        context: BatchContext,
        batch_row_nth: List[Hashable],
        runtime: ExecutionRuntime,
    ) -> None:
        """执行算子"""


__all__ = []
