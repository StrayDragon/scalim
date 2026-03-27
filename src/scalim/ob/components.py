# region imports

from typing import Any, List, Optional, Sequence, Tuple

from ..hooks import IExecutionHook
from .observer import Observer

# endregion


def split_components(
    components: Optional[Sequence[Any]],
) -> Tuple[Tuple[Observer, ...], Tuple[IExecutionHook, ...]]:
    observers: List[Observer] = []
    hooks: List[IExecutionHook] = []

    if not components:
        return (), ()

    for idx, component in enumerate(components):
        if isinstance(component, Observer):
            observers.append(component)
            continue
        if isinstance(component, IExecutionHook):
            hooks.append(component)
            continue
        msg = "Invalid component at index {}: type {} (expected Observer or IExecutionHook)".format(idx, type(component).__name__)
        raise TypeError(msg)

    return tuple(observers), tuple(hooks)


__all__ = [
    "split_components",
]
