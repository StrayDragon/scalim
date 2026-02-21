# region imports

import itertools
from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from ..adaptive.policy import AdaptivePolicy
from ..adaptive.tuning import AdaptiveTuning

# endregion

ChunkIterableFn = Callable[[Iterable[Any], int], Iterator[list[Any]]]


def chunk_iterable(iterable: Iterable[Any], chunk_size: int) -> Iterator[list[Any]]:
    it = iter(iterable)
    return iter(lambda: list(itertools.islice(it, chunk_size)), [])


@dataclass
class PipelineOverrides:
    chunk_iterable: ChunkIterableFn = chunk_iterable
    adaptive_executor_cls: type[Any] = ThreadPoolExecutor
    adaptive_process_executor_cls: type[Any] | None = None
    adaptive_async_executor_cls: type[Any] | None = None
    adaptive_min_parallel_tasks: int = 2
    adaptive_tuning: AdaptiveTuning | None = None
    adaptive_policy: AdaptivePolicy | None = None
    adaptive_loadref_executor_factory: Callable[[], Any] | None = None


__all__ = [
    "ChunkIterableFn",
    "PipelineOverrides",
    "chunk_iterable",
]
