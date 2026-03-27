"""`workflow` 运行期错误类型.

说明:
- `scalim.workflow` 不能依赖 `scalim.dsl`,因此此处定义 `workflow` 运行期使用的错误类型.
- `DSL` 适配层(`scalim.dsl.by_yaml.workflow_entrypoints`) 可以在必要时将该错误包装为 `DSL` 层的 `ScalimWorkflowConfigError`.
"""

from ..exceptions import ScalimWorkflowError


class ScalimWorkflowConfigError(ScalimWorkflowError):
    path: str

    def __init__(self, message: str, *, path: str = "") -> None:
        self.path = str(path or "")
        super(ScalimWorkflowConfigError, self).__init__(self._format(message))

    def _format(self, message: str) -> str:
        if not self.path:
            return str(message)
        return "{} (path={})".format(message, self.path)


__all__ = [
    "ScalimWorkflowConfigError",
]
