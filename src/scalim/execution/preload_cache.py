import contextlib
import copy
import threading
from collections.abc import MutableMapping as MutableMappingABC
from typing import TYPE_CHECKING, Callable, Dict, Iterator, Optional

from ..typedefs import LoaderResultMapping
from ..vendor.compact.typing_extensionsx import override

if TYPE_CHECKING:
    from typing import MutableMapping as MutableMappingType

    _PreloadCacheBase = MutableMappingType[str, LoaderResultMapping]
else:
    _PreloadCacheBase = MutableMappingABC


class _InFlight(object):
    def __init__(self, *, owner_ident: int) -> None:
        self.owner_ident: int = owner_ident
        self.done: threading.Event = threading.Event()
        self.ref_count: int = 1
        self.value: Optional[LoaderResultMapping] = None
        self.error: Optional[BaseException] = None


def _clone_exception_for_reraise(exc: BaseException) -> BaseException:
    try:
        cloned = copy.copy(exc)
    except Exception:  # noqa: BLE001
        cloned = None
    if isinstance(cloned, BaseException):
        return cloned

    try:
        args = getattr(exc, "args", ())
        return exc.__class__(*args)
    except Exception:  # noqa: BLE001
        return exc


class PreloadCache(_PreloadCacheBase):
    """线程安全的 `preload_forever` 缓存容器(按 `source_id` 分桶去重).

    设计目标:
    - 支持跨多个 `runs` 共享 `preload_forever` 结果(`Workflow` 场景)
    - 并发下对单个 `source_id` 加锁,保证最多一次真实 `loader` 调用
    """

    def __init__(self) -> None:
        self._data: Dict[str, LoaderResultMapping] = {}
        self._inflight: Dict[str, _InFlight] = {}
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
        self._inflight = {}
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

    def _decref_inflight_and_maybe_cleanup(self, *, source_id: str, inflight: _InFlight, lock: threading.Lock) -> None:
        with lock:
            inflight.ref_count -= 1
            if inflight.ref_count > 0:
                return
            if self._inflight.get(source_id) is inflight:
                _ = self._inflight.pop(source_id, None)

    def _get_or_load_owner(
        self,
        *,
        source_id: str,
        inflight: _InFlight,
        lock: threading.Lock,
        load_fn: Callable[[], LoaderResultMapping],
    ) -> LoaderResultMapping:
        try:
            value = load_fn()
        except BaseException as exc:
            stored_error = _clone_exception_for_reraise(exc)
            with contextlib.suppress(Exception):
                stored_error = stored_error.with_traceback(None)
            with lock:
                inflight.error = stored_error
                inflight.value = None
            inflight.done.set()
            raise
        with lock:
            self._data[source_id] = value
            inflight.value = value
            inflight.error = None
        inflight.done.set()
        return value

    def _get_or_load_waiter(
        self,
        *,
        source_id: str,
        inflight: _InFlight,
        lock: threading.Lock,
    ) -> LoaderResultMapping:
        _ = inflight.done.wait()
        with lock:
            if source_id in self._data:
                return self._data[source_id]
        if inflight.error is not None:
            raise _clone_exception_for_reraise(inflight.error)
        if inflight.value is not None:
            return inflight.value
        msg = "PreloadCache internal error: inflight done but missing value/error for source_id: {!r}".format(source_id)
        raise RuntimeError(msg)

    def get_or_load(self, source_id: str, load_fn: Callable[[], LoaderResultMapping]) -> LoaderResultMapping:
        if source_id in self._data:
            return self._data[source_id]

        lock = self._lock_for(source_id)
        current_ident = threading.get_ident()
        is_owner = False
        with lock:
            if source_id in self._data:
                return self._data[source_id]

            inflight = self._inflight.get(source_id)
            if inflight is None:
                inflight = _InFlight(owner_ident=current_ident)
                self._inflight[source_id] = inflight
                is_owner = True
            elif inflight.owner_ident == current_ident:
                msg = "Detected recursive preload for the same source_id: {!r}".format(source_id)
                raise RuntimeError(msg)
            else:
                inflight.ref_count += 1

        if is_owner:
            try:
                return self._get_or_load_owner(source_id=source_id, inflight=inflight, lock=lock, load_fn=load_fn)
            finally:
                self._decref_inflight_and_maybe_cleanup(source_id=source_id, inflight=inflight, lock=lock)

        try:
            return self._get_or_load_waiter(source_id=source_id, inflight=inflight, lock=lock)
        finally:
            self._decref_inflight_and_maybe_cleanup(source_id=source_id, inflight=inflight, lock=lock)

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
