"""`workflow` 路径解析(稳定导入路径).

说明:
- 提供更明确的路径解析导入路径,降低 `CLI` 与 `runtime` 的耦合
- 当前实现仍位于 `workflow_config.py`,此处仅做 `re-export`
- 运行时需兼容 `Python 3.6`
"""

from .workflow_config import resolve_workflow_demand_path

__all__ = [
    "resolve_workflow_demand_path",
]
