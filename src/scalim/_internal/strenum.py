"""`enum.StrEnum`(`Python 3.11+`) 的运行时兜底。

运行时下界当前为 `3.10`(见根 `ROADMAP.md`):下界到达 `3.11` 时必须删除本模块,
调用方改用标准库 `enum.StrEnum`(路线图棘轮步骤)。

多参调用分支(`encoding`/`errors`/过多参数)在运行时被 `EnumMeta.__call__`
先行拦截,属上游防御性死代码,以 `# pragma: no cover` + `allow-no-cover` 审计;
可达语义(`str()` 返回 `value`/成员查找/`auto` 小写)见
`tests/governance/test_internal_strenum.py`。
"""

import sys
from enum import Enum

from typing_extensions import Self, override

if sys.version_info >= (3, 11):  # pragma: no cover  # pragma: allow-no-cover floor>=3.11 时整模块删除
    from enum import StrEnum  # pyright: ignore[reportUnreachable]
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

        @override
        def __str__(self) -> str:
            # 对齐 `Python 3.11+` 的 `enum.StrEnum` 行为: `str(member)` 返回 `value` 而不是 `EnumClass.MEMBER`.
            return self.value

        def __new__(cls, *values: str) -> Self:
            "参数 `values` 必须已经是 `str` 类型"
            if len(values) > 3:  # noqa: PLR2004
                raise TypeError(f"`str()` 参数过多: {values!r}")  # noqa: EM102, TRY003  # pragma: no cover  # pragma: allow-no-cover EnumMeta.__call__ 先行拦截,不可达
            if len(values) == 1:  # noqa: SIM102
                # 必须是字符串
                if not isinstance(values[0], str):  # pragma: no cover  # pragma: allow-no-cover EnumMeta.__call__ 值查找先行,不可达
                    raise TypeError(f"参数必须是字符串,但得到: {values[0]!r}")  # noqa: EM102, TRY003
            if len(values) >= 2:  # noqa: PLR2004, SIM102  # pragma: no cover  # pragma: allow-no-cover EnumMeta.__call__ 先行拦截,不可达
                # 检查 `encoding` 参数是否为字符串
                if not isinstance(values[1], str):
                    raise TypeError(f"`encoding` 参数必须是字符串,但得到: {values[1]!r}")  # noqa: EM102, TRY003
            if len(values) == 3:  # noqa: PLR2004, SIM102  # pragma: no cover  # pragma: allow-no-cover EnumMeta.__call__ 先行拦截,不可达
                # 检查 `errors` 参数是否为字符串
                if not isinstance(values[2], str):
                    raise TypeError(f"`errors` 参数必须是字符串,但得到: {values[2]!r}")  # noqa: EM102, TRY003
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, _start: int, _count: int, _last_values: list[str]) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
            """
            返回成员名的小写版本.
            """
            return name.lower()


__all__ = ()
