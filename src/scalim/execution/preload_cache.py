import contextlib
import copy
import math
import threading
import time
import traceback
from collections.abc import MutableMapping as MutableMappingABC
from typing import TYPE_CHECKING, Callable, Dict, Iterator, Optional

from .._internal import loggingx
from ..typedefs import LoaderResultMapping
from ..vendor.compact.typing_extensionsx import override

if TYPE_CHECKING:
    from typing import MutableMapping as MutableMappingType

    _PreloadCacheBase = MutableMappingType[str, LoaderResultMapping]
else:
    _PreloadCacheBase = MutableMappingABC


class _InFlight(object):
    def __init__(
        self,
        *,
        owner_ident: int,
        signature_digest: Optional[str] = None,
        owner_callsite: Optional[str] = None,
    ) -> None:
        self.owner_ident: int = owner_ident
        self.signature_digest: Optional[str] = signature_digest
        self.owner_callsite: Optional[str] = owner_callsite
        self.done: threading.Event = threading.Event()
        self.ref_count: int = 1
        self.value: Optional[LoaderResultMapping] = None
        self.error: Optional[BaseException] = None


class PreloadCacheWaitDiagnostics(object):
    """`PreloadCache` `inflight` 等待诊断配置(默认关闭).

    说明:
    - 当 `enabled=False` 时,`waiter` 路径保持单次 `Event.wait()` (不引入循环/时间计算开销).
    - 仅在显式开启后,当等待超过阈值才输出告警 (便于定位卡住的 `source_id`).
    """

    def __init__(
        self,
        *,
        enabled: bool,
        warn_after_s: float = 30.0,
        repeat_every_s: Optional[float] = None,
        capture_owner_callsite: bool = False,
    ) -> None:
        self.enabled: bool = bool(enabled)

        warn_after = float(warn_after_s)
        if not math.isfinite(warn_after) or warn_after < 0:
            msg = "warn_after_s must be a finite non-negative float"
            raise ValueError(msg)
        self.warn_after_s: float = warn_after

        repeat_every = None if repeat_every_s is None else float(repeat_every_s)
        if repeat_every is not None and (not math.isfinite(repeat_every) or repeat_every <= 0):
            msg = "repeat_every_s must be a finite positive float"
            raise ValueError(msg)
        self.repeat_every_s: Optional[float] = repeat_every

        self.capture_owner_callsite: bool = bool(capture_owner_callsite)

    @classmethod
    def disabled(cls) -> "PreloadCacheWaitDiagnostics":
        return cls(enabled=False)


class PreloadCacheSignatureGuardrail(object):
    """`PreloadCache` `signature` 护栏配置(默认关闭).

    用途:
    - 当多个执行共享同一个 `PreloadCache` 时,用于检测同一 `source_id` 是否被不同 `signature_digest` 复用.
    - 默认关闭: 不改变既有行为.
    """

    def __init__(self, *, enabled: bool, policy: str = "error") -> None:
        self.enabled: bool = bool(enabled)
        self.policy: str = str(policy or "").strip() or "error"
        if self.policy not in ("error", "warn"):
            msg = "policy must be 'error' or 'warn'"
            raise ValueError(msg)

    @classmethod
    def disabled(cls) -> "PreloadCacheSignatureGuardrail":
        return cls(enabled=False)


def _clone_exception_for_reraise(exc: BaseException) -> BaseException:
    try:
        cloned = copy.copy(exc)
    except Exception:  # noqa: BLE001
        cloned = None
    if isinstance(cloned, BaseException):
        return cloned

    try:
        args = exc.args
        return exc.__class__(*args)
    except Exception:  # noqa: BLE001
        return exc


class PreloadCache(_PreloadCacheBase):
    """线程安全的 `preload_forever` 缓存容器(按 `source_id` 分桶去重).

    设计目标:
    - 支持跨多个 `runs` 共享 `preload_forever` 结果(`Workflow` 场景)
    - 并发下对单个 `source_id` 加锁,保证最多一次真实 `loader` 调用
    """

    def __init__(
        self,
        *,
        wait_diagnostics: Optional[PreloadCacheWaitDiagnostics] = None,
        signature_guardrail: Optional[PreloadCacheSignatureGuardrail] = None,
    ) -> None:
        self._data: Dict[str, LoaderResultMapping] = {}
        self._inflight: Dict[str, _InFlight] = {}
        self._signature_digests: Dict[str, str] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock: threading.Lock = threading.Lock()
        self._wait_diagnostics: PreloadCacheWaitDiagnostics = wait_diagnostics or PreloadCacheWaitDiagnostics.disabled()
        self._signature_guardrail: PreloadCacheSignatureGuardrail = signature_guardrail or PreloadCacheSignatureGuardrail.disabled()

    def __getstate__(self) -> Dict[str, object]:
        # 仅序列化数据,锁在反序列化后重建.
        # 说明:
        # - `adaptive` 的 `process` 后端会 `pickle` `preloaded_cache`,因此此对象必须可被 `pickle`.
        # - 共享锁只在同一进程内有意义.
        return {
            "_data": self._data,
            "_signature_digests": self._signature_digests,
        }

    def __setstate__(self, state: Dict[str, object]) -> None:
        raw_data = state.get("_data", {})
        if not isinstance(raw_data, dict):
            raw_data = {}
        self._data = raw_data  # type: ignore[assignment]
        raw_signatures = state.get("_signature_digests", {})
        if not isinstance(raw_signatures, dict):
            raw_signatures = {}
        self._signature_digests = raw_signatures  # type: ignore[assignment]
        self._inflight = {}
        self._locks = {}
        self._global_lock = threading.Lock()
        self._wait_diagnostics = PreloadCacheWaitDiagnostics.disabled()
        self._signature_guardrail = PreloadCacheSignatureGuardrail.disabled()

    @override
    def __getitem__(self, key: str) -> LoaderResultMapping:
        with self._lock_for(key):
            return self._data[key]

    @override
    def __setitem__(self, key: str, value: LoaderResultMapping) -> None:
        # 并发加载请优先使用 `get_or_load()`; 该方法仅直接写入缓存数据.
        with self._lock_for(key):
            self._data[key] = value

    @override
    def __delitem__(self, key: str) -> None:
        with self._lock_for(key):
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
            if self._signature_guardrail.enabled and inflight.signature_digest:
                self._signature_digests[source_id] = str(inflight.signature_digest)
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
        diagnostics = self._wait_diagnostics
        if not diagnostics.enabled:
            _ = inflight.done.wait()
        else:
            wait_start = time.monotonic()
            next_warn_after_s = diagnostics.warn_after_s
            poll_s = _compute_poll_interval_s(diagnostics)
            while True:
                if inflight.done.wait(timeout=poll_s):
                    break
                wait_s = time.monotonic() - wait_start
                if wait_s < next_warn_after_s:
                    continue
                _emit_inflight_wait_slow_warning(
                    source_id=source_id,
                    wait_s=wait_s,
                    inflight=inflight,
                    diagnostics=diagnostics,
                )
                if diagnostics.repeat_every_s is None:
                    next_warn_after_s = float("inf")
                else:
                    next_warn_after_s += diagnostics.repeat_every_s
        with lock:
            if source_id in self._data:
                return self._data[source_id]
        if inflight.error is not None:
            raise _clone_exception_for_reraise(inflight.error)
        if inflight.value is not None:
            return inflight.value
        msg = "PreloadCache internal error: inflight done but missing value/error for source_id: {!r}".format(source_id)
        raise RuntimeError(msg)

    @property
    def signature_guardrail_enabled(self) -> bool:
        return bool(self._signature_guardrail.enabled)

    def _guardrail_digest_or_none(self, signature_digest: Optional[str], *, source_id: str) -> Optional[str]:
        if not self._signature_guardrail.enabled:
            return None
        return self._normalize_signature_digest(signature_digest, source_id=source_id)

    def _handle_signature_mismatch(
        self,
        *,
        source_id: str,
        cached_digest: str,
        requested_digest: str,
    ) -> None:
        policy = str(self._signature_guardrail.policy)
        hint = "do not reuse the same PreloadCache across different demands/contexts; create a new cache per run or use WorkflowCachePool."
        msg = "{}signature digest mismatch: {} | hint: {}".format(
            loggingx.prefix("preload-cache"),
            loggingx.format_kv(
                source_id=str(source_id),
                cached_digest=str(cached_digest),
                requested_digest=str(requested_digest),
                policy=policy,
            ),
            hint,
        )
        if policy == "warn":
            logger = loggingx.get_logger("preload-cache")
            logger.warning(msg)
            return
        raise RuntimeError(msg)

    def _normalize_signature_digest(self, signature_digest: Optional[str], *, source_id: str) -> str:
        digest = str(signature_digest or "").strip()
        if not digest:
            msg = "PreloadCache signature guardrail is enabled but signature_digest is missing for source_id: {!r}".format(source_id)
            raise ValueError(msg)
        return digest

    def _guardrail_check_cached_locked(self, *, source_id: str, digest: Optional[str]) -> None:
        if digest is None:
            return
        cached = self._signature_digests.get(source_id)
        if cached is None:
            self._signature_digests[source_id] = digest
            return
        if cached != digest:
            self._handle_signature_mismatch(source_id=source_id, cached_digest=cached, requested_digest=digest)

    def _guardrail_check_inflight_locked(self, *, source_id: str, inflight: _InFlight, digest: Optional[str]) -> None:
        if digest is None:
            return
        existing = inflight.signature_digest
        if existing is None:
            inflight.signature_digest = digest
            return
        if existing != digest:
            self._handle_signature_mismatch(source_id=source_id, cached_digest=str(existing), requested_digest=str(digest))

    def _create_inflight(self, *, owner_ident: int, digest: Optional[str]) -> _InFlight:
        owner_callsite = None
        diagnostics = self._wait_diagnostics
        if diagnostics.enabled and diagnostics.capture_owner_callsite:
            owner_callsite = _capture_owner_callsite()
        return _InFlight(owner_ident=owner_ident, signature_digest=digest, owner_callsite=owner_callsite)

    def get_or_load(
        self,
        source_id: str,
        load_fn: Callable[[], LoaderResultMapping],
        *,
        signature_digest: Optional[str] = None,
    ) -> LoaderResultMapping:
        digest = self._guardrail_digest_or_none(signature_digest, source_id=source_id)
        if digest is None and source_id in self._data:
            return self._data[source_id]

        lock = self._lock_for(source_id)
        current_ident = threading.get_ident()
        is_owner = False
        with lock:
            if source_id in self._data:
                self._guardrail_check_cached_locked(source_id=source_id, digest=digest)
                return self._data[source_id]

            inflight = self._inflight.get(source_id)
            if inflight is None:
                inflight = self._create_inflight(owner_ident=current_ident, digest=digest)
                self._inflight[source_id] = inflight
                is_owner = True
            elif inflight.owner_ident == current_ident:
                msg = "Detected recursive preload for the same source_id: {!r}".format(source_id)
                raise RuntimeError(msg)
            else:
                self._guardrail_check_inflight_locked(source_id=source_id, inflight=inflight, digest=digest)
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


def _capture_owner_callsite() -> str:
    # 仅用于诊断模式: 尽量保持简短、稳定、且不包含不必要的栈深信息.
    stack = traceback.extract_stack(limit=12)
    for frame in reversed(stack[:-1]):
        filename = str(frame.filename or "")
        if filename.endswith("preload_cache.py"):
            continue
        func = str(frame.name or "")
        lineno = int(frame.lineno or 0)
        return "{}:{}:{}".format(filename, lineno, func)
    return "(unknown)"


def _compute_poll_interval_s(diagnostics: PreloadCacheWaitDiagnostics) -> float:
    # 默认: 1s 轮询;当阈值很小(例如测试场景)时,用更小的轮询避免错过告警.
    candidates = [1.0, diagnostics.warn_after_s]
    if diagnostics.repeat_every_s is not None:
        candidates.append(diagnostics.repeat_every_s)
    poll_s = min(candidates)
    return max(0.01, float(poll_s))


def _emit_inflight_wait_slow_warning(
    *,
    source_id: str,
    wait_s: float,
    inflight: _InFlight,
    diagnostics: PreloadCacheWaitDiagnostics,
) -> None:
    logger = loggingx.get_logger("preload-cache")
    msg = "{}inflight wait slow: {}".format(
        loggingx.prefix("preload-cache"),
        loggingx.format_kv(
            source_id=str(source_id),
            wait_s=round(float(wait_s), 3),
            warn_after_s=diagnostics.warn_after_s,
            repeat_every_s=diagnostics.repeat_every_s,
            owner_thread_ident=inflight.owner_ident,
            waiter_thread_ident=threading.get_ident(),
            owner_callsite=inflight.owner_callsite,
        ),
    )
    logger.warning(msg)


__all__ = (
    "PreloadCache",
    "PreloadCacheSignatureGuardrail",
    "PreloadCacheWaitDiagnostics",
)
