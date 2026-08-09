"""`LoadRef` `keys` 分片并行的运行级策略(`Python` 策略面).

分层心智:

- `parallel_mode="adaptive"`: 同一批次内多个**独立** `LoadRef` 之间重叠等待.
- 分片并行(本模块): 同一个 `LoadRef(keys)` 步骤内,分片产生的**多片**之间重叠等待.
- `parallel_mode="seq"` 或未 `opt-in`: 全部串行(默认).

分片大小与并行 `SSOT` 优先 `LookupChunking.sized(..., parallel=True)`(YAML `lookup_chunk_size` 已迁出).
遗留平铺 `parallelize_lookup_chunks=True` 仍可作为兼容开关,但不是推荐写法.
分片并行不是第三种 `parallel_mode`,而是运行级的**附加许可**.
"""

import threading
from typing import Optional

from ..typedefs import ParallelMode
from ..vendor.dataclassesx import dataclass
from .adaptive._internal.loadref_scheduler_support import resolve_adaptive_max_workers
from .lookup_chunking import normalize_optional_max_chunk_workers


@dataclass(frozen=True)
class LookupChunkParallelismPolicy:
    """分片并行策略(运行级;`adaptive` 工作线程子运行时会继承同一实例)."""

    parallelize_lookup_chunks: bool = False
    """是否允许同一 `LoadRef(keys)` 步骤内的多个分片并行(默认关闭)."""

    max_chunk_workers: Optional[int] = None
    """可选:单步分片扇出上限(`None` 表示仅受全局在途帽 `W` 与分片数限制)."""

    def __post_init__(self) -> None:
        if not isinstance(self.parallelize_lookup_chunks, bool):
            msg = "LookupChunkParallelismPolicy.parallelize_lookup_chunks must be a boolean"
            raise TypeError(msg)

        object.__setattr__(
            self,
            "max_chunk_workers",
            normalize_optional_max_chunk_workers(
                self.max_chunk_workers,
                label="LookupChunkParallelismPolicy.max_chunk_workers",
            ),
        )

    @classmethod
    def disabled(cls) -> "LookupChunkParallelismPolicy":
        return cls()

    def is_enabled_for(self, run_parallel_mode: ParallelMode) -> bool:
        """仅 `adaptive` 运行 + 显式 `opt-in` 才启用(`seq` 永不分片并行)."""
        return bool(self.parallelize_lookup_chunks) and run_parallel_mode == "adaptive"


def resolve_chunk_inflight_capacity(max_workers: int) -> int:
    """全局在途 `ref-loader` 调用帽 = `adaptive` 解析后的 `workers` `W`(复用同一护栏)."""
    return resolve_adaptive_max_workers(max_workers)


def build_chunk_inflight_semaphore(capacity: int) -> "threading.BoundedSemaphore":
    """构造进程内共享的在途帽信号量(容量应为 `resolve_chunk_inflight_capacity(...)` 的结果)."""
    return threading.BoundedSemaphore(max(1, int(capacity)))


__all__ = (
    "LookupChunkParallelismPolicy",
    "build_chunk_inflight_semaphore",
    "resolve_chunk_inflight_capacity",
)
