import pytest

from scalim.typedefs import FailurePolicy, normalize_failure_policy


def test_normalize_failure_policy_defaults_to_all_fail_on_none_and_empty() -> None:
    assert normalize_failure_policy(None) == "all_fail"
    assert normalize_failure_policy("") == "all_fail"
    assert normalize_failure_policy("   ") == "all_fail"


def test_normalize_failure_policy_accepts_enum_and_normalizes_string_variants() -> None:
    assert normalize_failure_policy(FailurePolicy.ALL_FAIL) == "all_fail"
    assert normalize_failure_policy(FailurePolicy.PRIMARY_ONLY) == "primary_only"
    assert normalize_failure_policy(" PRIMARY-ONLY ") == "primary_only"


def test_normalize_failure_policy_rejects_non_string_inputs() -> None:
    with pytest.raises(TypeError, match="policy must be a str"):
        _ = normalize_failure_policy(1, label="policy")  # type: ignore[arg-type]


def test_normalize_failure_policy_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="policy must be one of"):
        _ = normalize_failure_policy("bad", label="policy")
