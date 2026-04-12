# pragma: allow-c901-file plan: c90
"""`workflow` 共享输出资源: 基础设施(内部模块).

说明:
- 该模块仅承载通用的错误/写锁/事件发射与资源管理器基类
- 具体资源类型实现位于同目录的 `resources_*` 子模块
- 运行时需兼容 `Python 3.6`
"""

import math
import os
import tempfile
import time
from abc import ABC, abstractmethod
from contextlib import suppress
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .._internal import loggingx
from ..events import (
    EVENT_WORKFLOW_RESOURCE_COMMIT,
    EVENT_WORKFLOW_RESOURCE_CREATE,
    EVENT_WORKFLOW_RESOURCE_DISCARD,
    EVENT_WORKFLOW_RESOURCE_WRITE,
)
from ..events._events import (
    WorkflowResourceCommitEvent,
    WorkflowResourceCreateEvent,
    WorkflowResourceDiscardEvent,
    WorkflowResourceWriteEvent,
)
from ..exceptions import ScalimWorkflowError
from ..execution import versioned_outputs
from ..vendor.dataclassesx import dataclass


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


@dataclass(frozen=True)
class _StagedOutput:
    resource_type: str
    resource_id: str
    workflow_node_id: str
    staged_path: str
    final_path: str


class _WorkflowResourceManagerBase(ABC):
    """工作流级共享输出资源管理器基类(延迟提交 + 原子落盘)."""

    _workflow_exec_id: str
    _instrumentation: Any
    _workbook_defs: Dict[str, str]
    _workbook_allow_formulas: Dict[str, bool]
    _csv_defs: Dict[str, str]
    _sheetbook_defs: Dict[str, object]
    _workbooks: Dict[str, object]
    _csvs: Dict[str, object]
    _sheetbooks: Dict[str, object]
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
        csv_defs: Mapping[str, str],
        sheetbook_defs: Mapping[str, object],
        output_staging_dir_name: str = ".scalim-staging",
        output_staging_keep_on_success: bool = False,
        output_staging_keep_on_failure: bool = True,
    ) -> None:
        self._workflow_exec_id = str(workflow_exec_id)
        self._instrumentation = instrumentation
        self._workbook_defs = dict(workbook_defs)
        self._workbook_allow_formulas = dict(workbook_allow_formulas or {})
        self._csv_defs = dict(csv_defs)
        self._sheetbook_defs = dict(sheetbook_defs)
        self._workbooks = {}
        self._csvs = {}
        self._sheetbooks = {}
        self._output_staging_dir_name = self._normalize_output_staging_dir_name(output_staging_dir_name)
        self._output_staging_keep_on_success = bool(output_staging_keep_on_success)
        self._output_staging_keep_on_failure = bool(output_staging_keep_on_failure)
        self._staged_outputs = []

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
                        "hint=check_permissions_and_disk_space_or_set_workflow.options.output_staging.keep_on_success=true",
                    ],
                ) from exc

            self._emit_resource_commit(
                workflow_node_id=str(node_id),
                resource_type=str(item.resource_type),
                resource_id=str(item.resource_id),
                path=str(final_path),
            )
            if not self._output_staging_keep_on_success:
                self._cleanup_output_staging_exec_dir_for_final_path(final_path)

        # 成功发布后才写入版本 `manifest` 并更新 `latest` 指示 (`root` 维度 `last-writer-wins`)。
        by_root: Dict[str, Dict[str, Dict[str, str]]] = {}
        for item in staged:
            parsed = versioned_outputs.parse_versioned_output_path(Path(str(item.final_path)))
            if str(parsed.version_id) != str(self._workflow_exec_id):
                msg = "Workflow published output version_id mismatch: expected={!r}, got={!r} (path={!r})".format(
                    str(self._workflow_exec_id), str(parsed.version_id), str(item.final_path)
                )
                raise ScalimWorkflowWriteError(msg)
            root_key = str(parsed.root)
            entry = by_root.setdefault(root_key, {"books": {}, "files": {}})
            if str(parsed.kind) == "books":
                entry["books"][str(parsed.artifact_id)] = str(parsed.artifact_relpath)
            elif str(parsed.kind) == "files":
                entry["files"][str(parsed.artifact_id)] = str(parsed.artifact_relpath)

        created_at_unix_s = int(time.time())
        for root_key, payload in by_root.items():
            layout = versioned_outputs.ensure_output_root_layout(Path(str(root_key)))
            _ = versioned_outputs.write_version_manifest(
                layout,
                version_id=str(self._workflow_exec_id),
                created_at_unix_s=created_at_unix_s,
                books=payload.get("books"),
                files=payload.get("files"),
            )
            _ = versioned_outputs.update_latest(
                layout,
                version_id=str(self._workflow_exec_id),
                version_manifest_relpath=versioned_outputs.version_manifest_relpath(version_id=str(self._workflow_exec_id)),
            )

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

    def _get_or_create_plan(
        self,
        *,
        resource_type: str,
        resource_id: str,
        plans: Dict[str, object],
        create_fn: Callable[[], object],
        on_create: Callable[[object], None],
    ) -> object:
        _ = str(resource_type)
        key = str(resource_id)
        existing = plans.get(key)
        if existing is not None:
            return existing

        plan = create_fn()
        on_create(plan)
        plans[key] = plan
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
        self._publish_staged_outputs()

    def discard_all(self, *, workflow_node_id: str, reason: str) -> None:
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
    "ScalimWorkflowWriteError",
    "WorkflowResourceManagerBase",
    "WorkflowResourceWaitDiagnostics",
)

# 对外提供非私有别名,避免类型检查对跨模块私有符号的告警.
WorkflowResourceManagerBase = _WorkflowResourceManagerBase
