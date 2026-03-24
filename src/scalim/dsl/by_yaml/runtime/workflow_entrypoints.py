"""`workflow` 运行入口(稳定导入路径).

约束:
- 该模块对外保持稳定导入路径,内部实现可迁移/拆分
- 运行时需兼容 `Python 3.6`
"""

from typing import Any

from . import workflow_execute as _workflow_execute
from .workflow_compile import compile_workflow_ir
from .workflow_execute import (
    WorkflowArtifactsDirectory,
    WorkflowCtxStore,
    WorkflowRunFailedError,
    ensure_json_like,
    iter_ctx_directives,
    render_ctx_directives,
)
from .workflow_report import WorkflowResult, WorkflowRunError, WorkflowRunOutcome


def run_ir(*args: Any, **kwargs: Any) -> Any:
    from ....execution.run_ir import run_ir as _run_ir  # noqa: PLC0415

    return _run_ir(*args, **kwargs)


def run_workflow(*args: Any, **kwargs: Any) -> Any:
    # 单测可通过 `monkeypatch.setattr(workflow_entrypoints, "run_ir", ...)` 劫持执行器;
    # 并可通过 `run_workflow(..., run_ir_fn=...)` 做每次调用级别的显式注入(避免并发串扰).
    if "run_ir_fn" not in kwargs:
        kwargs["run_ir_fn"] = run_ir
    return _workflow_execute.run_workflow(*args, **kwargs)


# 兼容: 单测/内部使用点仍在引用旧的私有符号名.
_WorkflowArtifactsDirectory = WorkflowArtifactsDirectory
_WorkflowCtxStore = WorkflowCtxStore
_compile_workflow_ir = compile_workflow_ir
_ensure_json_like = ensure_json_like
_iter_ctx_directives = iter_ctx_directives
_render_ctx_directives = render_ctx_directives

__all__ = [
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunFailedError",
    "WorkflowRunOutcome",
    "_WorkflowArtifactsDirectory",
    "_WorkflowCtxStore",
    "_compile_workflow_ir",
    "_ensure_json_like",
    "_iter_ctx_directives",
    "_render_ctx_directives",
    "compile_workflow_ir",
    "run_workflow",
]
