# pragma: allow-c901-file plan: c90
"""`workflow` 共享输出资源: 基础设施(内部模块).

说明:
- 该模块仅承载通用的错误/写锁/事件发射与资源管理器基类
- 具体资源类型实现位于同目录的 `resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

import math
import os
import socket
import tempfile
import threading
import time
import traceback
from abc import ABC, abstractmethod
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, cast

from .._internal import loggingx
from .._internal.utils.exceptions import clone_exception_for_reraise
from ..events import (
    EVENT_DIAGNOSTIC_WARNING,
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
)
from ..events._events import (
    DiagnosticWarningEvent,
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
)
from ..exceptions import ScalimWorkflowError
from ..vendor.dataclassesx import dataclass

_WRITE_LOCK_SUFFIX = ".scalim.lock"


@dataclass
class WorkflowResourceWaitDiagnostics:
    """共享资源 `joinable get-or-create` 的 `waiter` 等待诊断配置(默认关闭).

    说明:
    - 当 `enabled=False` 且 `max_wait_s` 未配置时,`waiter` 路径保持单次 `Event.wait()` (不引入循环/时间计算开销).
    - 仅在显式开启后,当等待超过阈值才输出告警 (便于定位卡住的资源创建).
    """

    enabled: bool
    warn_after_s: float = 30.0
    repeat_every_s: Optional[float] = None
    capture_owner_callsite: bool = False

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)

        warn_after = float(self.warn_after_s)
        if not math.isfinite(warn_after) or warn_after < 0:
            msg = "warn_after_s must be a finite non-negative float"
            raise ValueError(msg)
        self.warn_after_s = warn_after

        repeat_every = None if self.repeat_every_s is None else float(self.repeat_every_s)
        if repeat_every is not None and (not math.isfinite(repeat_every) or repeat_every <= 0):
            msg = "repeat_every_s must be a finite positive float"
            raise ValueError(msg)
        self.repeat_every_s = repeat_every

        self.capture_owner_callsite = bool(self.capture_owner_callsite)

    @classmethod
    def disabled(cls) -> "WorkflowResourceWaitDiagnostics":
        return cls(enabled=False)


class ScalimWorkflowWriteError(ScalimWorkflowError):
    diff: Optional[List[str]]

    def __init__(self, message: str, *, diff: Optional[List[str]] = None) -> None:
        super(ScalimWorkflowWriteError, self).__init__(message)
        self.diff = list(diff) if diff is not None else None


class _InFlightCreate:
    def __init__(
        self,
        *,
        owner_thread_ident: int,
        owner_callsite: Optional[str] = None,
    ) -> None:
        self.owner_thread_ident: int = int(owner_thread_ident)
        self.owner_callsite: Optional[str] = owner_callsite
        self.done: threading.Event = threading.Event()
        self.error: Optional[BaseException] = None


@dataclass(frozen=True)
class _StagedOutput:
    resource_type: str
    resource_id: str
    workflow_node_id: str
    staged_path: str
    final_path: str


def _capture_owner_callsite() -> str:
    # 仅用于诊断模式: 尽量保持简短、稳定、且不包含不必要的栈深信息.
    stack = traceback.extract_stack(limit=12)
    for frame in reversed(stack[:-1]):
        filename = str(frame.filename or "")
        if filename.endswith("resources_base.py"):
            continue
        func = str(frame.name or "")
        lineno = int(frame.lineno or 0)
        return "{}:{}:{}".format(filename, lineno, func)
    return "(unknown)"


def _compute_poll_interval_s(diagnostics: WorkflowResourceWaitDiagnostics, *, max_wait_s: Optional[float]) -> float:
    # 默认: 1s 轮询;当阈值很小(例如测试场景)时,用更小的轮询避免错过告警/超时.
    candidates: List[float] = [1.0, float(diagnostics.warn_after_s)]
    if diagnostics.repeat_every_s is not None:
        candidates.append(float(diagnostics.repeat_every_s))
    if max_wait_s is not None:
        candidates.append(float(max_wait_s))
    poll_s = min(candidates)
    return max(0.01, float(poll_s))


def _read_lock_owner_info(lock_path: Path) -> Tuple[Dict[str, str], Optional[float]]:
    info: Dict[str, str] = {}
    mtime_s = None
    try:
        st = lock_path.stat()
    except FileNotFoundError:
        return info, None
    except OSError:
        st = None
    if st is not None:
        try:
            mtime_s = float(st.st_mtime)
        except Exception:  # noqa: BLE001
            mtime_s = None

    try:
        raw = lock_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return info, mtime_s
    for raw_line in raw.splitlines():
        line = str(raw_line or "").strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = str(k or "").strip()
        v = str(v or "").strip()
        if not k:
            continue
        info[str(k)] = str(v)
    return info, mtime_s


def _acquire_write_lock(  # noqa: C901, PLR0912
    output_path: str,
    *,
    owner: Optional[Mapping[str, object]] = None,
    stale_after_s: Optional[float] = None,
    force: bool = False,
) -> Path:
    lock_path = Path(str(output_path) + _WRITE_LOCK_SUFFIX)
    stale_after = None if stale_after_s is None else float(stale_after_s)
    if stale_after is not None and (not math.isfinite(stale_after) or stale_after < 0):
        msg = "stale_after_s must be a finite non-negative float"
        raise ValueError(msg)

    max_force_attempts = 3
    attempts = 0
    while True:
        attempts += 1
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            lock_info, lock_mtime_s = _read_lock_owner_info(lock_path)
            # 另一个写入方可能已创建锁文件, 但还未完成写入持有者 `owner` 元信息(极小窗口, 线程/进程调度可触发).
            # 这里短暂重试读取, 仅用于改善诊断信息,仍保持 `fail-fast`(不等待锁释放).
            if not lock_info:
                for _ in range(5):
                    time.sleep(0.01)
                    lock_info, lock_mtime_s = _read_lock_owner_info(lock_path)
                    if lock_info:
                        break
            lock_age_s = None
            if lock_mtime_s is not None:
                lock_age_s = max(0.0, float(time.time()) - float(lock_mtime_s))
            if stale_after is not None and lock_age_s is not None and lock_age_s >= float(stale_after) and bool(force):
                with suppress(Exception):
                    lock_path.unlink()
                if attempts < max_force_attempts:
                    continue

            diff: List[str] = [
                "lock_path={!r}".format(str(lock_path)),
            ]
            if lock_age_s is not None:
                diff.append("lock_age_s={}".format(round(float(lock_age_s), 3)))
            for k in sorted(lock_info.keys()):
                diff.append("lock_owner.{}={!r}".format(str(k), str(lock_info.get(k) or "")))
            if stale_after is not None:
                diff.append("stale_after_s={}".format(float(stale_after)))
                diff.append("force={}".format(bool(force)))
            diff.append("hint=delete_lock_file_if_safe:{!r}".format(str(lock_path)))

            msg = "Output path is locked (possible concurrent writers): output_path={!r}".format(str(output_path))
            raise ScalimWorkflowWriteError(msg, diff=diff) from None

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            _ = f.write("pid={}\n".format(os.getpid()))
            _ = f.write("created_at_unix_s={}\n".format(int(time.time())))
            with suppress(Exception):
                _ = f.write("hostname={}\n".format(socket.gethostname()))
            if owner:
                for k, v in owner.items():
                    key = str(k or "").strip()
                    if not key:
                        continue
                    _ = f.write("{}={}\n".format(key, str(v)))
        return lock_path


def _release_write_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


class _WorkflowResourceManagerBase(ABC):
    """工作流级共享输出资源管理器基类(延迟提交 + 原子落盘)."""

    _workflow_exec_id: str
    _instrumentation: Any
    _workbook_defs: Dict[str, str]
    _workbook_allow_formulas: Dict[str, bool]
    _workbook_write_lock: Dict[str, bool]
    _csv_defs: Dict[str, str]
    _csv_write_lock: Dict[str, bool]
    _sheetbook_defs: Dict[str, object]
    _workbooks: Dict[str, object]
    _csvs: Dict[str, object]
    _sheetbooks: Dict[str, object]
    _inflight_workbooks: Dict[str, _InFlightCreate]
    _inflight_csvs: Dict[str, _InFlightCreate]
    _lock: threading.Lock
    _wait_diagnostics: WorkflowResourceWaitDiagnostics
    _max_wait_s: Optional[float]
    _output_staging_dir_name: str
    _output_staging_keep_on_success: bool
    _output_staging_keep_on_failure: bool
    _staged_outputs: List[_StagedOutput]

    def __init__(
        self,
        *,
        workflow_exec_id: str,
        instrumentation: Any,
        workbook_defs: Mapping[str, str],
        workbook_allow_formulas: Optional[Mapping[str, bool]] = None,
        workbook_write_lock: Optional[Mapping[str, bool]] = None,
        csv_defs: Mapping[str, str],
        csv_write_lock: Optional[Mapping[str, bool]] = None,
        sheetbook_defs: Mapping[str, object],
        wait_diagnostics: Optional[WorkflowResourceWaitDiagnostics] = None,
        max_wait_s: Optional[float] = None,
        output_staging_dir_name: str = ".scalim-staging",
        output_staging_keep_on_success: bool = False,
        output_staging_keep_on_failure: bool = True,
    ) -> None:
        self._workflow_exec_id = str(workflow_exec_id)
        self._instrumentation = instrumentation
        self._workbook_defs = dict(workbook_defs)
        self._workbook_allow_formulas = dict(workbook_allow_formulas or {})
        # 注意: `workbook_write_lock` 由上游编译/执行层传入; 默认空映射表示不启用 `write_lock`。
        # 历史 `workbook` 资源的默认值由执行层设置(通常为 `True`); `books.kind=xlsx_file` 默认 `False` 且可由 `YAML` 显式配置.
        self._workbook_write_lock = dict(workbook_write_lock or {})
        self._csv_defs = dict(csv_defs)
        self._csv_write_lock = dict(csv_write_lock or {})
        self._sheetbook_defs = dict(sheetbook_defs)
        self._workbooks = {}
        self._csvs = {}
        self._sheetbooks = {}
        self._inflight_workbooks = {}
        self._inflight_csvs = {}
        self._lock = threading.Lock()
        self._wait_diagnostics = wait_diagnostics or WorkflowResourceWaitDiagnostics.disabled()
        self._max_wait_s = self._normalize_max_wait_s(max_wait_s)
        self._output_staging_dir_name = self._normalize_output_staging_dir_name(output_staging_dir_name)
        self._output_staging_keep_on_success = bool(output_staging_keep_on_success)
        self._output_staging_keep_on_failure = bool(output_staging_keep_on_failure)
        self._staged_outputs = []

    def _normalize_max_wait_s(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        max_wait = float(value)
        if not math.isfinite(max_wait) or max_wait <= 0:
            msg = "max_wait_s must be a finite positive float"
            raise ValueError(msg)
        return float(max_wait)

    def _normalize_output_staging_dir_name(self, value: str) -> str:
        dir_name = str(value or "").strip()
        if not dir_name:
            msg = "output_staging_dir_name must be a non-empty string"
            raise ValueError(msg)
        if dir_name in (".", "..") or "/" in dir_name or "\\" in dir_name:
            msg = "output_staging_dir_name must be a simple directory name (no separators)"
            raise ValueError(msg)
        return str(dir_name)

    def _staging_path_for_final_output(self, final_path: str) -> str:
        fp = str(final_path or "").strip()
        if not fp:
            msg = "final_path must be a non-empty string"
            raise ValueError(msg)
        out = Path(fp)
        return str(out.parent / str(self._output_staging_dir_name) / str(self._workflow_exec_id) / str(out.name))

    def _register_staged_output(
        self,
        *,
        resource_type: str,
        resource_id: str,
        workflow_node_id: str,
        staged_path: str,
        final_path: str,
    ) -> None:
        self._staged_outputs.append(
            _StagedOutput(
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                workflow_node_id=str(workflow_node_id),
                staged_path=str(staged_path),
                final_path=str(final_path),
            )
        )

    def _cleanup_output_staging_exec_dir_for_final_path(self, final_path: str) -> None:
        # 尝试清理空的暂存目录(尽力而为): `<final_dir>/<dir_name>/<workflow_exec_id>` (即 `staging` 目录)
        p = Path(str(final_path)).parent / str(self._output_staging_dir_name) / str(self._workflow_exec_id)
        with suppress(Exception):
            p.rmdir()

    def _create_publish_temp_path(self, final_path: str) -> str:
        output_dir = Path(str(final_path)).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix=".publish.tmp", dir=str(output_dir))
        os.close(fd)
        return str(temp_path)

    def _copy_file_atomic(self, src_path: str, *, final_path: str) -> None:
        src = Path(str(src_path))
        dst = str(final_path)
        temp_path = self._create_publish_temp_path(dst)
        temp_obj = Path(temp_path)
        try:
            with src.open("rb") as r, temp_obj.open("wb") as w:
                while True:
                    chunk = r.read(1024 * 1024)
                    if not chunk:
                        break
                    _ = w.write(chunk)
            _ = temp_obj.replace(dst)
        except Exception:
            with suppress(Exception):
                temp_obj.unlink()
            raise

    def _publish_staged_outputs(self) -> None:  # noqa: C901
        if not self._staged_outputs:
            return

        def _resolve_write_lock(item: _StagedOutput) -> bool:
            if str(item.resource_type) == "workbook":
                return bool(self._workbook_write_lock.get(str(item.resource_id), False))
            if str(item.resource_type) == "csv":
                return bool(self._csv_write_lock.get(str(item.resource_id), False))
            if str(item.resource_type) == "sheetbook":
                raw_def = self._sheetbook_defs.get(str(item.resource_id))
                try:
                    return bool(cast("Any", raw_def).export_write_lock)  # pragma: allow-cast sheetbook def boundary
                except AttributeError:
                    return False
            return False

        def _sort_key(item: _StagedOutput) -> Tuple[str, str, str]:
            return (str(item.resource_type), str(item.resource_id), str(item.final_path))

        staged = sorted(self._staged_outputs, key=_sort_key)
        for item in staged:
            staged_path = str(item.staged_path)
            final_path = str(item.final_path)
            node_id = str(item.workflow_node_id)

            if not Path(staged_path).exists():
                msg = "Missing staged output for publish: {}".format(
                    loggingx.format_kv(
                        resource_type=item.resource_type, resource_id=item.resource_id, staged_path=staged_path, final_path=final_path
                    )
                )
                raise ScalimWorkflowWriteError(msg)

            Path(final_path).parent.mkdir(parents=True, exist_ok=True)

            write_lock = _resolve_write_lock(item)
            lock_path = None
            if write_lock:
                owner = {
                    "workflow_exec_id": self._workflow_exec_id,
                    "resource_type": str(item.resource_type),
                    "resource_id": str(item.resource_id),
                    "workflow_node_id": str(node_id),
                    "staged_path": str(staged_path),
                }
                try:
                    lock_path = _acquire_write_lock(final_path, owner=owner)
                except ScalimWorkflowWriteError as exc:
                    diff = list(exc.diff or [])
                    diff.extend(
                        [
                            "resource_type={!r}".format(str(item.resource_type)),
                            "resource_id={!r}".format(str(item.resource_id)),
                            "workflow_node_id={!r}".format(str(node_id)),
                            "staged_path={!r}".format(str(staged_path)),
                            "final_path={!r}".format(str(final_path)),
                            "keep_on_success={!r}".format(bool(self._output_staging_keep_on_success)),
                            "write_lock={!r}".format(bool(write_lock)),
                        ]
                    )
                    raise ScalimWorkflowWriteError(str(exc), diff=diff) from exc

            try:
                if self._output_staging_keep_on_success:
                    self._copy_file_atomic(staged_path, final_path=final_path)
                else:
                    _ = Path(staged_path).replace(final_path)
            except Exception as exc:
                msg = "Publish staged output failed: {}: {}".format(type(exc).__name__, exc)
                raise ScalimWorkflowWriteError(
                    msg,
                    diff=[
                        "resource_type={!r}".format(str(item.resource_type)),
                        "resource_id={!r}".format(str(item.resource_id)),
                        "workflow_node_id={!r}".format(str(node_id)),
                        "staged_path={!r}".format(str(staged_path)),
                        "final_path={!r}".format(str(final_path)),
                        "keep_on_success={!r}".format(bool(self._output_staging_keep_on_success)),
                        "write_lock={!r}".format(bool(write_lock)),
                        "lock_path={!r}".format(str(lock_path)) if lock_path is not None else "lock_path=<none>",
                        "hint=check_permissions_and_disk_space_or_set_workflow.options.output_staging.keep_on_success=true",
                    ],
                ) from exc
            finally:
                if lock_path is not None:
                    _release_write_lock(lock_path)

            self._emit_resource_commit(
                workflow_node_id=str(node_id),
                resource_type=str(item.resource_type),
                resource_id=str(item.resource_id),
                path=str(final_path),
            )
            if not self._output_staging_keep_on_success:
                self._cleanup_output_staging_exec_dir_for_final_path(final_path)

        self._staged_outputs = []

    def _cleanup_staged_outputs_on_failure(self) -> None:
        if self._output_staging_keep_on_failure:
            return
        for item in list(self._staged_outputs):
            staged_path = str(item.staged_path)
            final_path = str(item.final_path)
            with suppress(Exception):
                Path(staged_path).unlink()
            with suppress(Exception):
                self._cleanup_output_staging_exec_dir_for_final_path(final_path)
        self._staged_outputs = []

    def _emit_inflight_wait_slow_warning(
        self,
        *,
        resource_type: str,
        resource_id: str,
        wait_kind: str,
        wait_s: float,
        inflight_state: _InFlightCreate,
    ) -> None:
        diagnostics = self._wait_diagnostics
        lookup_key = {
            "resource_type": str(resource_type),
            "resource_id": str(resource_id),
            "wait_kind": str(wait_kind),
            "wait_s": round(float(wait_s), 3),
            "warn_after_s": float(diagnostics.warn_after_s),
            "repeat_every_s": diagnostics.repeat_every_s,
            "max_wait_s": self._max_wait_s,
            "owner_thread_ident": inflight_state.owner_thread_ident,
            "waiter_thread_ident": threading.get_ident(),
            "owner_callsite": inflight_state.owner_callsite,
        }
        event = DiagnosticWarningEvent(
            message="Workflow resource inflight wait slow",
            source_id=None,
            field_id=None,
            lookup_key=lookup_key,
            row_id=None,
        )
        meta = {
            "workflow_exec_id": self._workflow_exec_id,
            "resource_type": str(resource_type),
            "resource_id": str(resource_id),
        }

        try:
            _ = self._instrumentation.emit(EVENT_DIAGNOSTIC_WARNING, event, meta=meta)
        except Exception:  # noqa: BLE001
            logger = loggingx.get_logger("workflow-resources")
            msg = "{}inflight wait slow: {}".format(loggingx.prefix("workflow-resources"), loggingx.format_kv(lookup_key))
            logger.warning(msg)

    def _wait_for_inflight_done(
        self,
        *,
        inflight_state: _InFlightCreate,
        resource_type: str,
        resource_id: str,
        wait_kind: str,
    ) -> None:
        diagnostics = self._wait_diagnostics
        max_wait_s = self._max_wait_s
        if not diagnostics.enabled and max_wait_s is None:
            _ = inflight_state.done.wait()
            return

        wait_start = time.monotonic()
        next_warn_after_s = diagnostics.warn_after_s
        poll_s = _compute_poll_interval_s(diagnostics, max_wait_s=max_wait_s)
        while True:
            if inflight_state.done.wait(timeout=poll_s):
                return
            wait_s = time.monotonic() - wait_start

            if max_wait_s is not None and wait_s >= max_wait_s:
                msg = "Workflow resource inflight wait timeout: {}".format(
                    loggingx.format_kv(
                        resource_type=str(resource_type),
                        resource_id=str(resource_id),
                        wait_kind=str(wait_kind),
                        wait_s=round(float(wait_s), 3),
                        max_wait_s=float(max_wait_s),
                        owner_thread_ident=inflight_state.owner_thread_ident,
                        waiter_thread_ident=threading.get_ident(),
                        owner_callsite=inflight_state.owner_callsite,
                        hint="check_owner_thread_hang_or_adjust_workflow.options.resources_wait",
                    )
                )
                raise ScalimWorkflowWriteError(msg)

            if not diagnostics.enabled or wait_s < next_warn_after_s:
                continue

            self._emit_inflight_wait_slow_warning(
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                wait_kind=str(wait_kind),
                wait_s=wait_s,
                inflight_state=inflight_state,
            )
            if diagnostics.repeat_every_s is None:
                next_warn_after_s = float("inf")
            else:
                next_warn_after_s += diagnostics.repeat_every_s

    def _drain_inflight(self, *, wait_kind: str) -> None:
        while True:
            with self._lock:
                workbook_items = list(self._inflight_workbooks.items())
                csv_items = list(self._inflight_csvs.items())
            if not workbook_items and not csv_items:
                return
            for inflight_id, inflight_state in workbook_items:
                self._wait_for_inflight_done(
                    inflight_state=inflight_state,
                    resource_type="workbook",
                    resource_id=str(inflight_id),
                    wait_kind=str(wait_kind),
                )
            for inflight_id, inflight_state in csv_items:
                self._wait_for_inflight_done(
                    inflight_state=inflight_state,
                    resource_type="csv",
                    resource_id=str(inflight_id),
                    wait_kind=str(wait_kind),
                )

    def _new_inflight_state(self) -> _InFlightCreate:
        owner_callsite = None
        diagnostics = self._wait_diagnostics
        if diagnostics.enabled and diagnostics.capture_owner_callsite:
            owner_callsite = _capture_owner_callsite()
        return _InFlightCreate(
            owner_thread_ident=threading.get_ident(),
            owner_callsite=owner_callsite,
        )

    def _store_inflight_error_and_cleanup(
        self,
        *,
        key: str,
        inflight: Dict[str, _InFlightCreate],
        inflight_state: _InFlightCreate,
        exc: BaseException,
    ) -> None:
        stored_error = clone_exception_for_reraise(exc)
        with self._lock:
            inflight_state.error = stored_error
            if inflight.get(key) is inflight_state:
                _ = inflight.pop(key, None)

    def _get_joinable_plan_waiter(
        self,
        *,
        resource_type: str,
        resource_id: str,
        key: str,
        plans: Dict[str, object],
        inflight_state: _InFlightCreate,
    ) -> object:
        self._wait_for_inflight_done(
            inflight_state=inflight_state,
            resource_type=str(resource_type),
            resource_id=str(resource_id),
            wait_kind="join",
        )
        with self._lock:
            existing = plans.get(key)
            error = inflight_state.error
        if existing is not None:
            return existing
        if error is not None:
            raise clone_exception_for_reraise(error)
        msg = (  # pragma: no cover  # pragma: allow-no-cover unreachable: inflight always stores plan or error
            "WorkflowResourceManager internal error: inflight done but missing plan/error for resource_id: {!r}".format(key)
        )
        raise RuntimeError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: inflight always stores plan or error

    def _get_joinable_plan_owner(
        self,
        *,
        key: str,
        plans: Dict[str, object],
        inflight: Dict[str, _InFlightCreate],
        inflight_state: _InFlightCreate,
        create_fn: Callable[[], object],
        on_create: Callable[[object], None],
    ) -> object:
        try:
            plan = create_fn()
            on_create(plan)
        except BaseException as exc:
            self._store_inflight_error_and_cleanup(key=key, inflight=inflight, inflight_state=inflight_state, exc=exc)
            raise
        else:
            with self._lock:
                plans[key] = plan
                if inflight.get(key) is inflight_state:
                    _ = inflight.pop(key, None)
                inflight_state.error = None
            return plan
        finally:
            inflight_state.done.set()

    def _get_or_create_joinable_plan(
        self,
        *,
        resource_type: str,
        resource_id: str,
        plans: Dict[str, object],
        inflight: Dict[str, _InFlightCreate],
        create_fn: Callable[[], object],
        on_create: Callable[[object], None],
    ) -> object:
        key = str(resource_id)
        with self._lock:
            existing = plans.get(key)
            if existing is not None:
                return existing
            inflight_state = inflight.get(key)
            if inflight_state is None:
                inflight_state = self._new_inflight_state()
                inflight[key] = inflight_state
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            return self._get_joinable_plan_waiter(
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                key=key,
                plans=plans,
                inflight_state=inflight_state,
            )

        return self._get_joinable_plan_owner(
            key=key,
            plans=plans,
            inflight=inflight,
            inflight_state=inflight_state,
            create_fn=create_fn,
            on_create=on_create,
        )

    def _emit_resource_create(self, *, workflow_node_id: str, resource_type: str, resource_id: str, path: str) -> None:
        _ = self._instrumentation.emit(
            EVENT_WORKFLOW_RESOURCE_CREATE,
            WorkflowResourceCreateEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(workflow_node_id),
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                path=str(path),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    def _emit_resource_write(
        self,
        *,
        workflow_node_id: str,
        resource_type: str,
        resource_id: str,
        path: str,
        write_kind: str,
        action: str,
        input_node_id: Optional[str] = None,
        input_output_id: Optional[str] = None,
        sheet: Optional[str] = None,
    ) -> None:
        _ = self._instrumentation.emit(
            EVENT_WORKFLOW_RESOURCE_WRITE,
            WorkflowResourceWriteEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(workflow_node_id),
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                path=str(path),
                write_kind=str(write_kind),
                action=str(action),
                input_node_id=str(input_node_id) if input_node_id is not None else None,
                input_output_id=str(input_output_id) if input_output_id is not None else None,
                sheet=str(sheet) if sheet is not None else None,
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    def _emit_resource_commit(self, *, workflow_node_id: str, resource_type: str, resource_id: str, path: str) -> None:
        _ = self._instrumentation.emit(
            EVENT_WORKFLOW_RESOURCE_COMMIT,
            WorkflowResourceCommitEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(workflow_node_id),
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                path=str(path),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    def _emit_resource_discard(self, *, workflow_node_id: str, resource_type: str, resource_id: str, path: str, reason: str) -> None:
        _ = self._instrumentation.emit(
            EVENT_WORKFLOW_RESOURCE_DISCARD,
            WorkflowResourceDiscardEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(workflow_node_id),
                resource_type=str(resource_type),
                resource_id=str(resource_id),
                path=str(path),
                reason=str(reason),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    def commit_all(self) -> None:
        self._drain_inflight(wait_kind="commit_all")
        for plan in list(self._workbooks.values()):
            self._commit_workbook(plan)
        for plan in list(self._csvs.values()):
            self._commit_csv(plan)
        for plan in list(self._sheetbooks.values()):
            self._commit_sheetbook(plan)
        self._publish_staged_outputs()

    def discard_all(self, *, workflow_node_id: str, reason: str) -> None:
        self._drain_inflight(wait_kind="discard_all")
        for plan in list(self._workbooks.values()):
            self._discard_workbook(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))
        for plan in list(self._csvs.values()):
            self._discard_csv(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))
        for plan in list(self._sheetbooks.values()):
            self._discard_sheetbook(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))
        self._cleanup_staged_outputs_on_failure()

    @abstractmethod
    def _commit_workbook(self, plan: object) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    @abstractmethod
    def _commit_csv(self, plan: object) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    @abstractmethod
    def _commit_sheetbook(self, plan: object) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    @abstractmethod
    def _discard_workbook(
        self, plan: object, *, workflow_node_id: str, reason: str
    ) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    @abstractmethod
    def _discard_csv(
        self, plan: object, *, workflow_node_id: str, reason: str
    ) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError

    @abstractmethod
    def _discard_sheetbook(
        self, plan: object, *, workflow_node_id: str, reason: str
    ) -> None:  # pragma: no cover  # pragma: allow-no-cover abstract method
        raise NotImplementedError


__all__ = (
    "WRITE_LOCK_SUFFIX",
    "ScalimWorkflowWriteError",
    "WorkflowResourceManagerBase",
    "WorkflowResourceWaitDiagnostics",
    "acquire_write_lock",
    "release_write_lock",
)

# 对外提供非私有别名,避免类型检查对跨模块私有符号的告警.
WorkflowResourceManagerBase = _WorkflowResourceManagerBase
WRITE_LOCK_SUFFIX = _WRITE_LOCK_SUFFIX
acquire_write_lock = _acquire_write_lock
release_write_lock = _release_write_lock
