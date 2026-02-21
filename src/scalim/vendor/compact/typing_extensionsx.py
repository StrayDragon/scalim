from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict, TypeVar

# region override compat (stdlib: 3.12+)
try:
    from typing import override  # pyright: ignore[reportUnusedImport]
except ImportError:  # pragma: no cover
    try:
        from typing_extensions import override  # pyright: ignore[reportAssignmentType, reportUnusedImport]
    except ImportError:  # pragma: no cover
        F = TypeVar("F")

        def override(func: F) -> F:
            return func

# endregion


__all__ = ["Literal", "Self", "TypedDict", "override"]


# region Self compat (stdlib: 3.11+)
try:
    from typing import Self  # pyright: ignore[reportUnusedImport]  # noqa: PLC0414
except ImportError:  # pragma: no cover
    if TYPE_CHECKING:
        from typing_extensions import Self  # pyright: ignore[reportUnusedImport]
    else:
        Self = TypeVar("Self")
# endregion
