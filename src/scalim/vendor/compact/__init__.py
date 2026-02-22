import sys
from enum import Enum

from .typing_extensionsx import Self

if sys.version_info >= (3, 11):
    from enum import StrEnum  # pragma: no cover  # pyright: ignore[reportUnreachable]
else:
    # copied from https://github.com/python/cpython/blob/1ae900424b3c888d2b2cc97e6ef780717813d658/Lib/enum.py#L1365
    class ReprEnum(Enum):
        """
        Only changes the repr(), leaving str() and format() to the mixed-in type.
        """

    class StrEnum(str, ReprEnum):
        """
        Enum where members are also (and must be) strings
        """

        def __new__(cls, *values: str) -> Self:
            "values must already be of type `str`"
            if len(values) > 3:  # noqa: PLR2004
                raise TypeError(f"too many arguments for str(): {values!r}")  # noqa: EM102, TRY003
            value = str(*values)
            member = str.__new__(cls, value)
            member._value_ = value
            return member

        @staticmethod
        def _generate_next_value_(name: str, _start: int, _count: int, _last_values: list[str]) -> str:  # pyright: ignore[reportIncompatibleMethodOverride, reportImplicitOverride]
            """
            Return the lower-cased version of the member name.
            """
            return name.lower()
