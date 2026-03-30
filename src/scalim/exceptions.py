import os
from typing import Optional

REDACTED_ERROR_MESSAGE = "(redacted)"
_DEBUG_ERRORS_ENV = "SCALIM_DEBUG_ERRORS"


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


def _env_debug_errors_enabled() -> bool:
    raw = str(os.environ.get(_DEBUG_ERRORS_ENV, "") or "").strip().lower()
    return raw not in ("", "0", "false", "no", "off")


def safe_error_message(error: BaseException, *, debug: Optional[bool] = None) -> Optional[str]:
    """返回适用于对外输出的错误消息.

    默认策略:
    - `ScalimError`: 认为其 `__str__` 已遵循敏感信息治理约束,可直接输出.
    - 非 `ScalimError`: 默认脱敏为 `(redacted)`,仅在显式 `debug` 时输出 `str(error)`.

    `debug` 开关:
    - `debug=None`(默认): 由环境变量 `SCALIM_DEBUG_ERRORS` 决定.
    - `debug=True/False`: 强制覆盖.
    """

    debug_enabled = _env_debug_errors_enabled() if debug is None else bool(debug)
    if not isinstance(error, ScalimError) and not debug_enabled:
        return REDACTED_ERROR_MESSAGE

    try:
        return str(error)
    except Exception:  # noqa: BLE001
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
