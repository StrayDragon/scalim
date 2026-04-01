# region imports

import itertools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, Iterator, List, Optional, Type

from ...vendor.dataclassesx import dataclass
from ..adaptive.policy import AdaptivePolicy
from ..adaptive.tuning import AdaptiveTuning

# endregion

ChunkIterableFn = Callable[[Iterable[Any], int], Iterator[List[Any]]]


def chunk_iterable(iterable: Iterable[Any], chunk_size: int) -> Iterator[List[Any]]:
    it = iter(iterable)
    return iter(lambda: list(itertools.islice(it, chunk_size)), [])


@dataclass
class PipelineOverrides:
    chunk_iterable: ChunkIterableFn = chunk_iterable
    """将输入可迭代对象按 `chunk_size` 切分为块的函数."""

    adaptive_executor_cls: Type[Any] = ThreadPoolExecutor
    """自适应并发默认使用的执行器类型(线程池)."""

    adaptive_min_parallel_tasks: int = 2
    """每层最小并行任务数阈值(小于该值将倾向于串行)."""

    adaptive_tuning: Optional[AdaptiveTuning] = None
    """可选:自适应调优参数(将作为默认值,可能被策略覆盖)."""

    adaptive_policy: Optional[AdaptivePolicy] = None
    """可选:自适应策略(用于定制并行决策/后端选择/任务池分配)."""

    adaptive_loadref_executor_factory: Optional[Callable[[], Any]] = None
    """可选:为 `LoadRef` 关联加载创建执行器的工厂函数."""

    stage_perf_counter_fn: Optional[Callable[[], float]] = None
    """可选:阶段计时函数(默认使用系统计时)."""

    gc_collect_fn: Optional[Callable[[], int]] = None
    """可选:`GC` 回收函数(用于注入/测试)."""

    sys_module: Optional[object] = None
    """可选:`sys` 模块注入点(用于测试或兼容性处理)."""

    warnings_module: Optional[object] = None
    """可选:`warnings` 模块注入点(用于测试或兼容性处理)."""


__all__ = (
    "ChunkIterableFn",
    "PipelineOverrides",
    "chunk_iterable",
)
