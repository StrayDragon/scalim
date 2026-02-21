# region imports

from collections.abc import Sequence
from typing import Any

from ..hooks.base import IExecutionHook
from .observer import Observer

# endregion


def split_components(
    components: Sequence[Any] | None,
) -> tuple[tuple[Observer, ...], tuple[IExecutionHook, ...]]:
    observers: list[Observer] = []
    hooks: list[IExecutionHook] = []

    if not components:
        return (), ()

    for idx, component in enumerate(components):
        if isinstance(component, Observer):
            observers.append(component)
            continue
        if isinstance(component, IExecutionHook):
            hooks.append(component)
            continue
        msg = f"Invalid component at index {idx}: type {type(component).__name__} (expected Observer or IExecutionHook)"
        raise TypeError(msg)

    return tuple(observers), tuple(hooks)


__all__ = [
    "split_components",
]
