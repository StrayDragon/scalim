"""`workflow` 加载阶段实现(内部模块).

说明:
- 负责读取 `workflow` `YAML` 并解析为 `config`
- 运行时需兼容 `Python 3.6`
"""

from typing import Mapping, Optional, Tuple

from .workflow import WorkflowConfig, WorkflowConfigError, load_workflow_config


def load_workflow_config_from_path(
    workflow_yaml_path: str,
    *,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
) -> Tuple[str, WorkflowConfig]:
    workflow_path = str(workflow_yaml_path or "").strip()
    if not workflow_path:
        msg = "workflow_yaml_path is required"
        raise WorkflowConfigError(msg, path="(file)")
    wf = load_workflow_config(workflow_path, template_vars=template_vars, template_sandbox=template_sandbox)
    return workflow_path, wf


__all__ = [
    "load_workflow_config_from_path",
]
