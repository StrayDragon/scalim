import pytest

from scalim.typedefs import FailurePolicy, normalize_failure_policy, parse_failure_policy


def test_parse_failure_policy_defaults_to_all_fail_on_none_and_empty() -> None:
    assert parse_failure_policy(None) == "all_fail"
    assert parse_failure_policy("") == "all_fail"
    assert parse_failure_policy("   ") == "all_fail"


def test_failure_policy_accepts_enum_and_parses_string_variants() -> None:
    assert normalize_failure_policy(FailurePolicy.ALL_FAIL) == "all_fail"
    assert normalize_failure_policy(FailurePolicy.PRIMARY_ONLY) == "primary_only"
    assert parse_failure_policy(" PRIMARY-ONLY ") == "primary_only"


def test_parse_failure_policy_rejects_non_string_inputs() -> None:
    with pytest.raises(TypeError, match=r"policy must be a str"):
        _ = parse_failure_policy(1, label="policy")  # type: ignore[arg-type]


def test_parse_failure_policy_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match=r"Unknown policy"):
        _ = parse_failure_policy("bad", label="policy")


def test_normalize_failure_policy_rejects_string_literals() -> None:
    with pytest.raises(TypeError, match=r"policy must be a FailurePolicy"):
        _ = normalize_failure_policy("primary_only", label="policy")  # type: ignore[arg-type]
