"""`workflow` 注入/测试专用入口(内部模块;非稳定导入路径).

说明:
- 该模块仅用于测试/内部注入,避免把实现细节固化到对外 `API` 表面.
- 对外入口应使用 `scalim.dsl.yaml_dsl.run_workflow` 或 `scalim.dsl.yaml_dsl.workflow_entrypoints.run_workflow`.
"""

from typing import Callable, Optional

from ....execution.run_ir import ExecutionResult
from ....workflow.report import WorkflowResult
from ..workflow_entrypoints import WorkflowCompilationLike
from ..workflow_entrypoints import run_workflow_injected as _run_workflow_injected
from ..workflow_types import WorkflowRunOptions


def run_workflow_injected(
    workflow_yaml_path: str,
    *,
    options: WorkflowRunOptions,
    run_ir_fn: Optional[Callable[..., ExecutionResult]] = None,
    compile_demand_yaml_fn: Optional[Callable[..., WorkflowCompilationLike]] = None,
) -> WorkflowResult:
    return _run_workflow_injected(
        workflow_yaml_path,
        options=options,
        run_ir_fn=run_ir_fn,
        compile_demand_yaml_fn=compile_demand_yaml_fn,
    )


__all__ = ()
