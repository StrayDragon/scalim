import sys
from enum import Enum
from typing import List

from .typing_extensionsx import Self

if sys.version_info >= (3, 11):
    from enum import StrEnum  # pragma: no cover  # pyright: ignore[reportUnreachable]
else:
    # 从上游源码复制: `https://github.com/python/cpython/blob/1ae900424b3c888d2b2cc97e6ef780717813d658/Lib/enum.py#L1365`
    class ReprEnum(Enum):
        """
        仅改变 `repr()`,而 `str()` 与 `format()` 仍交由混入类型实现.
        """

    class StrEnum(str, ReprEnum):
        """
        成员也是(且必须是)字符串的枚举.
        """

        def __new__(cls, *values: str) -> Self:
            "参数 `values` 必须已经是 `str` 类型"
            if len(values) > 3:  # noqa: PLR2004
                raise TypeError(f"`str()` 参数过多: {values!r}")  # noqa: EM102, TRY003
            if len(values) == 1:  # noqa: SIM102
                # 必须是字符串
                if not isinstance(values[0], str):
                    raise TypeError(f"参数必须是字符串,但得到: {values[0]!r}")  # noqa: EM102, TRY003
            if len(values) >= 2:  # noqa: PLR2004, SIM102
                # 检查 `encoding` 参数是否为字符串
                if not isinstance(values[1], str):
                    raise TypeError(f"`encoding` 参数必须是字符串,但得到: {values[1]!r}")  # noqa: EM102, TRY003
            if len(values) == 3:  # noqa: PLR2004, SIM102
                # 检查 `errors` 参数是否为字符串
                if not isinstance(values[2], str):
                    raise TypeError(f"`errors` 参数必须是字符串,但得到: {values[2]!r}")  # noqa: EM102, TRY003
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, _start: int, _count: int, _last_values: List[str]) -> str:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
            """
            返回成员名的小写版本.
            """
            return name.lower()


__all__ = (
    "Self",
    "StrEnum",
)
