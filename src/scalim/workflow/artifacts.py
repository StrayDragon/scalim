"""`workflow` `artifacts` 模块(稳定导入路径).

说明:
- 本模块仅做符号重导出;实现 `SSOT` 在 `scalim.workflow.execute`.
- 运行时需兼容 `Python 3.6`.
"""

from .execute import WorkflowArtifactsDirectory

__all__ = ["WorkflowArtifactsDirectory"]
