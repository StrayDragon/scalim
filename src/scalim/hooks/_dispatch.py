from collections.abc import Callable
from typing import TypeVar

HookT = TypeVar("HookT")
EventT = TypeVar("EventT")
HandlerResultT = TypeVar("HandlerResultT")


class HookDispatchStrategy:
    """分发 `hook` 处理器;可插拔以定制事件扇出策略."""

    def dispatch(
        self,
        handler_pairs: tuple[tuple[HookT, Callable[[EventT], HandlerResultT]], ...],
        event: EventT,
        safe_call: Callable[[HookT, Callable[[EventT], HandlerResultT], EventT], None],
    ) -> None:
        for hook, handler in handler_pairs:
            safe_call(hook, handler, event)


__all__ = ()
