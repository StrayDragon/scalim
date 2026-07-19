from typing import Sequence, Tuple

from ...exceptions import ScalimExecutionError
from .strategy_unit import AdaptiveTaskKey


def _format_items(items: Sequence[str], *, limit: int = 10) -> str:
    if not items:
        return ""
    if len(items) <= int(limit):
        return ", ".join(items)
    remaining = len(items) - int(limit)
    return ", ".join(items[: int(limit)]) + ", ... (+{} more)".format(remaining)


class ScalimAdaptiveTaskTimeoutError(ScalimExecutionError):
    """`parallel_mode=\"adaptive\"` 任务等待超时(可捕获的稳定异常类型)."""

    timeout_seconds: float
    pending_task_keys: Tuple[AdaptiveTaskKey, ...]
    pending_field_keys: Tuple[str, ...]

    def __init__(
        self,
        *,
        timeout_seconds: float,
        pending_task_keys: Sequence[AdaptiveTaskKey],
        pending_field_keys: Sequence[str],
    ) -> None:
        self.timeout_seconds = float(timeout_seconds)
        self.pending_task_keys = tuple(pending_task_keys)
        self.pending_field_keys = tuple(str(x) for x in pending_field_keys)

        field_keys_text = _format_items(self.pending_field_keys)
        task_keys_text = _format_items([repr(x) for x in self.pending_task_keys])
        msg = "".join(
            [
                f"adaptive task wait timed out after {self.timeout_seconds:.3f}s: {len(self.pending_task_keys)} pending tasks. ",
                f"pending_field_keys=[{field_keys_text}]. pending_task_keys=[{task_keys_text}]. ",
                "Note: Python threads cannot be force-killed; consider isolating untrusted loader code in a subprocess.",
            ]
        )
        super().__init__(msg)


__all__ = ("ScalimAdaptiveTaskTimeoutError",)
