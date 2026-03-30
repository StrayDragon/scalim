from typing import Any, List

from scalim.execution.loader_retry import LoaderRetryContext


class TransientError(RuntimeError):
    pass


def load_orders() -> List[Any]:
    return [{"order_id": 1}]


def load_customers(**_kwargs: Any) -> dict:
    return {}


def should_retry(exc: Exception, ctx: LoaderRetryContext) -> bool:
    _ = ctx
    return isinstance(exc, TransientError)
