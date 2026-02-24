import pytest

import scalim.execution.loader_retry as lr
from scalim.execution.loader_retry import LoaderRetryPolicy, LoaderRetryPolicySpec, merge_loader_retry_policy


@pytest.mark.parametrize(
    "kwargs, error_type, match",
    [
        ({"enabled": 1}, TypeError, r"enabled must be a bool"),
        ({"enabled": True}, ValueError, r"enabled=true requires should_retry"),
        ({"should_retry": "nope"}, TypeError, r"should_retry must be callable"),
        ({"max_attempts": True}, TypeError, r"max_attempts must be an int"),
        ({"max_attempts": 0}, ValueError, r"max_attempts must be >= 1"),
        ({"max_attempts": 6}, ValueError, r"max_attempts must be <= 5"),
        ({"max_elapsed_seconds": True}, TypeError, r"max_elapsed_seconds must be a number"),
        ({"max_elapsed_seconds": 0}, ValueError, r"max_elapsed_seconds must be > 0"),
        ({"max_elapsed_seconds": 21}, ValueError, r"max_elapsed_seconds must be <="),
        ({"backoff": 1}, TypeError, r"backoff must be a string"),
        ({"backoff": "random"}, ValueError, r"backoff must be 'fixed' or 'exponential'"),
        ({"base_delay_seconds": True}, TypeError, r"base_delay_seconds must be a number"),
        ({"base_delay_seconds": -0.1}, ValueError, r"base_delay_seconds must be >= 0"),
        ({"max_delay_seconds": True}, TypeError, r"max_delay_seconds must be a number"),
        ({"max_delay_seconds": -1}, ValueError, r"max_delay_seconds must be >= 0"),
        ({"max_delay_seconds": 10}, ValueError, r"max_delay_seconds must be <="),
        ({"jitter": 1}, TypeError, r"jitter must be a bool"),
    ],
)
def test_loader_retry_policy_rejects_invalid_values(kwargs, error_type, match) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(error_type, match=match):
        _ = LoaderRetryPolicy(**kwargs)


def test_merge_loader_retry_policy_returns_base_when_spec_is_none() -> None:
    base = LoaderRetryPolicy.disabled()
    assert merge_loader_retry_policy(base, None) is base


def test_merge_loader_retry_policy_overrides_non_none_fields() -> None:
    base = LoaderRetryPolicy.disabled()
    spec = LoaderRetryPolicySpec(max_attempts=5)
    merged = merge_loader_retry_policy(base, spec)
    assert merged.max_attempts == 5


def test_truncate_message_handles_empty_and_long() -> None:
    assert lr._truncate_message("", max_len=200) == ""  # noqa: SLF001
    truncated = lr._truncate_message("x" * 500, max_len=10)  # noqa: SLF001
    assert truncated.endswith("...")
    assert len(truncated) == 10
