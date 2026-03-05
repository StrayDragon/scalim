from typing import TYPE_CHECKING, Any, TypeVar

# region py3.6 using 4.1.1 cannot import override
try:
    from typing_extensions import override  # pyright: ignore[reportAssignmentType, reportUnusedImport]
except ImportError:
    F = TypeVar("F")

    def override(func: F) -> F:
        return func

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
                return object()

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
