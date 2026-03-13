from typing import Any, List

from scalim.execution.loader_retry import LoaderRetryContext


class TransientError(RuntimeError):
    pass


_call_count_state = {"count": 0}


def reset() -> None:
    _call_count_state["count"] = 0


def get_call_count() -> int:
    return int(_call_count_state["count"])


def load_orders(**_kwargs: Any) -> List[Any]:
    _call_count_state["count"] += 1
    if _call_count_state["count"] == 1:
        msg = "模拟瞬态失败"
        raise TransientError(msg)
    return [{"order_id": 1}]


def should_retry(exc: Exception, ctx: LoaderRetryContext) -> bool:
    _ = ctx
    return isinstance(exc, TransientError)
