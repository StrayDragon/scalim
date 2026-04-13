"""工作流运行的资源/缓存生命周期助手(`c45 Phase 1b`)."""

import contextlib
from typing import List, Optional

from ..execution.workflow_cache_pool import WorkflowCachePool
from .artifacts import WorkflowArtifactsDirectory
from .errors import ScalimWorkflowConfigError
from .report import WorkflowRunOutcome
from .resources import ScalimWorkflowWriteError, WorkflowResourceManager


class WorkflowResourceLifecycle:
    """轻量封装: 统一 `cache_pool` 回收与资源 `commit`/`discard`/`cleanup`."""

    _rm: WorkflowResourceManager
    _artifacts: WorkflowArtifactsDirectory
    _cache_pool: Optional[WorkflowCachePool]

    def __init__(
        self,
        resource_manager: WorkflowResourceManager,
        artifacts_dir: WorkflowArtifactsDirectory,
        cache_pool: Optional[WorkflowCachePool],
    ) -> None:
        self._rm = resource_manager
        self._artifacts = artifacts_dir
        self._cache_pool = cache_pool

    def on_node_terminal(self, node_id: str, *, ok: bool) -> None:
        _ = ok
        if self._cache_pool is None:
            return
        self._cache_pool.on_workflow_node_done(str(node_id))

    def commit_or_discard(self, *, success: bool, discard_node_id: str = "__wf__discard") -> None:
        try:
            if bool(success):
                self._rm.commit_all()
            else:
                self._rm.discard_all(workflow_node_id=str(discard_node_id), reason="workflow_failed")
        except ScalimWorkflowWriteError as exc:
            with contextlib.suppress(Exception):
                self._rm.discard_all(workflow_node_id="__wf__discard", reason="resource_commit_failed")
            raise ScalimWorkflowConfigError(str(exc), path="workflow.resources") from exc

    def cleanup_finally(self, *, resources_finalized: bool) -> None:
        if not resources_finalized:
            with contextlib.suppress(Exception):
                self._rm.discard_all(workflow_node_id="__wf__discard", reason="workflow_finally")
        with contextlib.suppress(Exception):
            self._artifacts.discard_all_in_memory_csv_outputs()
        with contextlib.suppress(Exception):
            self._artifacts.discard_all_in_memory_rows_outputs()
        with contextlib.suppress(Exception):
            self._artifacts.discard_all_in_memory_rows()
        if self._cache_pool is not None:
            with contextlib.suppress(Exception):
                self._cache_pool.close()


def commit_workflow_resources(
    *,
    resource_manager: WorkflowResourceManager,
    outcomes: List[WorkflowRunOutcome],
    failed: Optional[WorkflowRunOutcome],
) -> None:
    """提交或丢弃工作流资源(保留旧入口以便测试/对拍)."""
    try:
        has_errors = any(o.error is not None for o in outcomes)
        if has_errors:
            discard_node_id = failed.run_id if failed is not None else "__wf__discard"
            resource_manager.discard_all(workflow_node_id=str(discard_node_id), reason="workflow_failed")
        else:
            resource_manager.commit_all()
    except ScalimWorkflowWriteError as exc:
        with contextlib.suppress(Exception):
            resource_manager.discard_all(workflow_node_id="__wf__discard", reason="resource_commit_failed")
        raise ScalimWorkflowConfigError(str(exc), path="workflow.resources") from exc


__all__ = ()
