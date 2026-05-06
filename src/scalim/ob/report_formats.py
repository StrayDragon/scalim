# region imports

from ..vendor.compact import StrEnum

# endregion


class ConsoleJsonlReportFormat(StrEnum):
    """通用观测器报告输出格式(封闭集合;可复用)."""

    AUTO = "auto"
    CONSOLE = "console"
    JSONL = "jsonl"
    NONE = "none"


__all__ = ("ConsoleJsonlReportFormat",)
