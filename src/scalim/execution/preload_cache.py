import threading
from collections.abc import MutableMapping as MutableMappingABC
from typing import TYPE_CHECKING, Callable, Dict, Iterator

from ..typedefs import LoaderResultMapping
from ..vendor.compact.typing_extensionsx import override

if TYPE_CHECKING:
    from typing import MutableMapping as MutableMappingType

    _PreloadCacheBase = MutableMappingType[str, LoaderResultMapping]
else:
    _PreloadCacheBase = MutableMappingABC


class PreloadCache(_PreloadCacheBase):
    """线程安全的 `preload_forever` 缓存容器(按 `source_id` 分桶去重).

    设计目标:
    - 支持跨多个 `runs` 共享 `preload_forever` 结果(`Workflow` 场景)
    - 并发下对单个 `source_id` 加锁,保证最多一次真实 `loader` 调用
    """

    def __init__(self) -> None:
        self._data: Dict[str, LoaderResultMapping] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock: threading.Lock = threading.Lock()

    def __getstate__(self) -> Dict[str, object]:
        # 仅序列化数据,锁在反序列化后重建.
        # 说明:
        # - `adaptive` 的 `process` 后端会 `pickle` `preloaded_cache`,因此此对象必须可被 `pickle`.
        # - 共享锁只在同一进程内有意义.
        return {"_data": self._data}

    def __setstate__(self, state: Dict[str, object]) -> None:
        raw_data = state.get("_data", {})
        if not isinstance(raw_data, dict):
            raw_data = {}
        self._data = raw_data  # type: ignore[assignment]
        self._locks = {}
        self._global_lock = threading.Lock()

    @override
    def __getitem__(self, key: str) -> LoaderResultMapping:
        return self._data[key]

    @override
    def __setitem__(self, key: str, value: LoaderResultMapping) -> None:
        self._data[key] = value

    @override
    def __delitem__(self, key: str) -> None:
        del self._data[key]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    @override
    def __len__(self) -> int:
        return len(self._data)

    def get_or_load(self, source_id: str, load_fn: Callable[[], LoaderResultMapping]) -> LoaderResultMapping:
        existing = self._data.get(source_id)
        if existing is not None:
            return existing

        lock = self._lock_for(source_id)
        with lock:
            existing = self._data.get(source_id)
            if existing is not None:
                return existing
            value = load_fn()
            self._data[source_id] = value
            return value

    def _lock_for(self, source_id: str) -> threading.Lock:
        with self._global_lock:
            lock = self._locks.get(source_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[source_id] = lock
            return lock


__all__ = [
    "PreloadCache",
]
