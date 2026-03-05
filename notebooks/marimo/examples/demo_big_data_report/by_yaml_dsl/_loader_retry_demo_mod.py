from typing import Any, List

from scalim.execution.loader_retry import LoaderRetryContext


class TransientError(RuntimeError):
    pass


_CALL_COUNT = 0


def reset() -> None:
    global _CALL_COUNT
    _CALL_COUNT = 0


def get_call_count() -> int:
    return _CALL_COUNT


def load_orders(**_kwargs: Any) -> List[Any]:
    global _CALL_COUNT
    _CALL_COUNT += 1
    if _CALL_COUNT == 1:
        raise TransientError("模拟瞬态失败")
    return [{"order_id": 1}]


def should_retry(exc: Exception, ctx: LoaderRetryContext) -> bool:
    _ = ctx
    return isinstance(exc, TransientError)
