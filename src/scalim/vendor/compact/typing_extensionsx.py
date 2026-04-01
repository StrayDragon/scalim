from typing import TYPE_CHECKING, Any, TypeVar

# region py3.6 using 4.1.1 cannot import override
try:
    from typing_extensions import override  # pyright: ignore[reportAssignmentType, reportUnusedImport]
except ImportError:
    F = TypeVar("F")

    def override(func: F) -> F:
        return func

# endregion


# region TypeGuard compat
try:
    from typing_extensions import TypeGuard  # pyright: ignore[reportUnusedImport]
except ImportError:
    if TYPE_CHECKING:
        from typing_extensions import TypeGuard  # pyright: ignore[reportUnusedImport]
    else:
        # 最小化兜底: 仅用于 `Python 3.6` 上注解求值通过; 类型收窄由类型检查器处理.
        class _TypeGuard:
            def __getitem__(self, item: Any) -> Any:
                return bool

        TypeGuard = _TypeGuard()
# endregion


# region Literal compat
try:
    from typing_extensions import Literal  # pyright: ignore[reportUnusedImport]
except ImportError:
    try:
        from typing import Literal  # pyright: ignore[reportUnusedImport]
    except ImportError:
        # 最小化的运行时兜底,用于在 `Python 3.6` 上进行注解求值.
        class _Literal:
            def __getitem__(self, item: Any) -> Any:
                return object

        Literal = _Literal()
# endregion


# region Self compat (typing_extensions < 4.0 or some 4.x versions)
try:
    from typing_extensions import Self  # pyright: ignore[reportUnusedImport]
except ImportError:
    if TYPE_CHECKING:
        from typing_extensions import Self  # pyright: ignore[reportUnusedImport]
    else:
        Self = TypeVar("Self")
# endregion


# region TypedDict compat
try:
    from typing_extensions import TypedDict  # pyright: ignore[reportUnusedImport, reportAssignmentType]
except ImportError:
    try:
        from typing import TypedDict  # pyright: ignore[reportUnusedImport, reportAssignmentType]
    except ImportError:
        # 最小化兜底:在 `Python 3.6` 上允许带 `total=...` 的类语法.
        class TypedDict(dict):  # pyright: ignore[reportMissingTypeArgument]
            def __init_subclass__(cls, **kwargs: Any) -> None:
                super().__init_subclass__()
# endregion


# region Protocol compat
try:
    from typing_extensions import Protocol  # pyright: ignore[reportUnusedImport, reportAssignmentType]
except ImportError:
    try:
        from typing import Protocol  # pyright: ignore[reportUnusedImport, reportAssignmentType]
    except ImportError:

        class Protocol(object):
            pass
# endregion


# region runtime_checkable compat
try:
    from typing_extensions import runtime_checkable  # pyright: ignore[reportUnusedImport]
except ImportError:
    try:
        from typing import runtime_checkable  # pyright: ignore[reportUnusedImport]
    except ImportError:
        C = TypeVar("C")

        def runtime_checkable(cls: C) -> C:
            return cls

# endregion

__all__ = ()
