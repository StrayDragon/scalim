from enum import Enum

import pytest

from scalim._internal.utils.policy import enum_values, parse_policy_value


class _BadPolicyEnum(Enum):
    A = 1


class _GoodPolicyEnum(Enum):
    A = "a"
    B = "b"


def test_enum_values_requires_builtin_str_values() -> None:
    with pytest.raises(TypeError, match=r"Enum _BadPolicyEnum must use builtin str values"):
        _ = enum_values(_BadPolicyEnum)


def test_parse_policy_value_rejects_none_without_default() -> None:
    with pytest.raises(TypeError, match=r"policy must not be None; expected one of: a/b"):
        _ = parse_policy_value(_GoodPolicyEnum, None, label="policy")


def test_parse_policy_value_accepts_builtin_str_without_normalizer() -> None:
    assert parse_policy_value(_GoodPolicyEnum, "a", label="policy") == "a"
