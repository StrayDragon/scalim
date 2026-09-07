"""`scalim._internal.strenum` 兼容兜底(`floor<3.11`)的可达语义测试.

语义基准为 `CPython 3.11+` 的 `enum.StrEnum`;`__new__` 的防御分支(多参/
非 `str` 值)被 `EnumMeta.__call__` 的值查找先行拦截(见模块内 `allow-no-cover`
标记),不在测试范围。
floor>=3.11 后本模块与测试一起删除。
"""

import pytest

from scalim._internal.strenum import StrEnum


class _Mode(StrEnum):
    A = "a"
    B = "b"


def test_member_is_str_and_value_semantics() -> None:
    assert isinstance(_Mode.A, str)
    assert _Mode.A == "a"
    assert _Mode("a") is _Mode.A


def test_str_returns_value_not_member_name() -> None:
    assert str(_Mode.A) == "a"
    assert f"{_Mode.B}" == "b"


def test_invalid_value_raises_value_error() -> None:
    # 非成员值由 `EnumMeta.__call__` 值查找拒绝,不进入 `StrEnum.__new__`
    with pytest.raises(ValueError, match="is not a valid"):
        _Mode(1)  # type: ignore[arg-type]


def test_auto_generates_lowercase_member() -> None:
    from enum import auto

    class _Auto(StrEnum):
        RED = auto()

    assert _Auto.RED.value == "red"
    assert str(_Auto.RED) == "red"
