"""`workflow` 共享输出资源: 基础设施(内部模块).

说明:
- 该模块仅承载通用的错误/写锁/事件发射与资源管理器基类
- 具体资源类型实现位于同目录的 `workflow_resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

import copy
import os
import threading
from abc import ABC, abstractmethod
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from ....events.catalog import (
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
)
from ....events.events import (
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
)

_WRITE_LOCK_SUFFIX = ".scalim.lock"


class WorkflowWriteError(RuntimeError):
    diff: Optional[List[str]]

    def __init__(self, message: str, *, diff: Optional[List[str]] = None) -> None:
        super(WorkflowWriteError, self).__init__(message)
        self.diff = list(diff) if diff is not None else None


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


class _InFlightCreate:
    def __init__(self) -> None:
        self.done: threading.Event = threading.Event()
        self.error: Optional[BaseException] = None


def _acquire_write_lock(output_path: str) -> Path:
    lock_path = Path(str(output_path) + _WRITE_LOCK_SUFFIX)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        msg = "Output path is locked (possible concurrent writers): output_path={!r}, lock_path={!r}".format(
            str(output_path),
            str(lock_path),
        )
        raise WorkflowWriteError(msg) from None
    with os.fdopen(fd, "w") as f:
        _ = f.write("pid={}\n".format(os.getpid()))
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
    _csv_defs: Dict[str, str]
    _sheetbook_defs: Dict[str, object]
    _workbooks: Dict[str, object]
    _csvs: Dict[str, object]
    _sheetbooks: Dict[str, object]
    _inflight_workbooks: Dict[str, _InFlightCreate]
    _inflight_csvs: Dict[str, _InFlightCreate]
    _lock: threading.Lock

    def __init__(
        self,
        *,
        workflow_exec_id: str,
        instrumentation: Any,
        workbook_defs: Mapping[str, str],
        csv_defs: Mapping[str, str],
        sheetbook_defs: Mapping[str, object],
    ) -> None:
        self._workflow_exec_id = str(workflow_exec_id)
        self._instrumentation = instrumentation
        self._workbook_defs = dict(workbook_defs)
        self._csv_defs = dict(csv_defs)
        self._sheetbook_defs = dict(sheetbook_defs)
        self._workbooks = {}
        self._csvs = {}
        self._sheetbooks = {}
        self._inflight_workbooks = {}
        self._inflight_csvs = {}
        self._lock = threading.Lock()

    def _get_or_create_joinable_plan(
        self,
        *,
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
                inflight_state = _InFlightCreate()
                inflight[key] = inflight_state
                is_owner = True
            else:
                is_owner = False

        if not is_owner:
            _ = inflight_state.done.wait()
            with self._lock:
                existing = plans.get(key)
                if existing is not None:
                    return existing
                error = inflight_state.error
            if error is not None:
                raise _clone_exception_for_reraise(error)
            msg = "WorkflowResourceManager internal error: inflight done but missing plan/error for resource_id: {!r}".format(
                key
            )  # pragma: no cover
            raise RuntimeError(msg)  # pragma: no cover

        try:
            plan = create_fn()
        except BaseException as exc:
            stored_error = _clone_exception_for_reraise(exc)
            with suppress(Exception):
                stored_error = stored_error.with_traceback(None)
            with self._lock:
                inflight_state.error = stored_error
                if inflight.get(key) is inflight_state:
                    _ = inflight.pop(key, None)
            inflight_state.done.set()
            raise

        with self._lock:
            plans[key] = plan
            if inflight.get(key) is inflight_state:
                _ = inflight.pop(key, None)
            inflight_state.error = None

        try:
            on_create(plan)
        finally:
            inflight_state.done.set()
        return plan

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
        for plan in list(self._workbooks.values()):
            self._commit_workbook(plan)
        for plan in list(self._csvs.values()):
            self._commit_csv(plan)
        for plan in list(self._sheetbooks.values()):
            self._commit_sheetbook(plan)

    def discard_all(self, *, workflow_node_id: str, reason: str) -> None:
        for plan in list(self._workbooks.values()):
            self._discard_workbook(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))
        for plan in list(self._csvs.values()):
            self._discard_csv(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))
        for plan in list(self._sheetbooks.values()):
            self._discard_sheetbook(plan, workflow_node_id=str(workflow_node_id), reason=str(reason))

    @abstractmethod
    def _commit_workbook(self, plan: object) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _commit_csv(self, plan: object) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _commit_sheetbook(self, plan: object) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _discard_workbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _discard_csv(self, plan: object, *, workflow_node_id: str, reason: str) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def _discard_sheetbook(self, plan: object, *, workflow_node_id: str, reason: str) -> None:  # pragma: no cover
        raise NotImplementedError


__all__ = [
    "WRITE_LOCK_SUFFIX",
    "WorkflowResourceManagerBase",
    "WorkflowWriteError",
    "_WorkflowResourceManagerBase",
    "_acquire_write_lock",
    "_release_write_lock",
    "acquire_write_lock",
    "release_write_lock",
]

# 对外提供非私有别名,避免类型检查对跨模块私有符号的告警.
WorkflowResourceManagerBase = _WorkflowResourceManagerBase
WRITE_LOCK_SUFFIX = _WRITE_LOCK_SUFFIX
acquire_write_lock = _acquire_write_lock
release_write_lock = _release_write_lock
