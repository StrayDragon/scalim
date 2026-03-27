from typing import Optional

REDACTED_ERROR_MESSAGE = "(redacted)"


class ScalimError(Exception):
    """`Scalim` 异常根类型.

    约束:
    - `scalim` 仓库内新增的自定义异常必须直接或间接继承该类型.
    - 该类型仅作为异常体系治理/兜底捕获边界;`message` 不作为稳定程序契约.
    """


class ScalimYamlError(ScalimError):
    """YAML DSL 相关异常基类."""


class ScalimExecutionError(ScalimError):
    """执行相关异常基类."""


class ScalimWorkflowError(ScalimError):
    """工作流相关异常基类."""


class ScalimObserverError(ScalimError):
    """观察者/钩子等可观测性相关异常基类."""


class ScalimInternalError(ScalimError):
    """框架内部错误基类(不应由用户输入直接触发)."""


def safe_error_type(error: BaseException) -> str:
    return type(error).__name__


def safe_error_message(error: BaseException) -> Optional[str]:
    # 对于 `scalim` 自定义异常,默认认为其 `__str__` 已遵循敏感信息治理约束.
    if isinstance(error, ScalimError):
        return str(error)

    # 对于非 `scalim` 异常,无法保证 `str(error)` 不包含敏感信息;默认脱敏.
    return REDACTED_ERROR_MESSAGE


__all__ = [
    "REDACTED_ERROR_MESSAGE",
    "ScalimError",
    "ScalimExecutionError",
    "ScalimInternalError",
    "ScalimObserverError",
    "ScalimWorkflowError",
    "ScalimYamlError",
    "safe_error_message",
    "safe_error_type",
]
