import pytest


def test_parse_csv_patterns_strips_and_ignores_empties() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import _parse_csv_patterns

    assert _parse_csv_patterns("") == ()
    assert _parse_csv_patterns(" , ,, ") == ()
    assert _parse_csv_patterns("a,b") == ("a", "b")
    assert _parse_csv_patterns(" a , ,  b  ,") == ("a", "b")


def test_call_by_memoize_field_filter_allow_and_deny() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import CallByMemoizeFieldFilter

    f0 = CallByMemoizeFieldFilter(allow_patterns=(), deny_patterns=())
    assert f0.allows("any_field") is True

    f1 = CallByMemoizeFieldFilter(allow_patterns=("foo*",), deny_patterns=())
    assert f1.allows("foo") is True
    assert f1.allows("foo_bar") is True
    assert f1.allows("bar") is False

    f2 = CallByMemoizeFieldFilter(allow_patterns=("foo*",), deny_patterns=("foo_bar",))
    assert f2.allows("foo") is True
    assert f2.allows("foo_bar") is False


def test_call_by_memoize_field_filter_deny_overrides_allow() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import CallByMemoizeFieldFilter

    f = CallByMemoizeFieldFilter(allow_patterns=("foo*",), deny_patterns=("foo*",))
    assert f.allows("foo") is False
    assert f.allows("foo_bar") is False


def test_call_by_memoize_env_parsers() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import _parse_bool_env, _parse_int_env_positive_or_zero

    assert _parse_int_env_positive_or_zero("0") == 0
    assert _parse_int_env_positive_or_zero("-1") == 0
    assert _parse_int_env_positive_or_zero("2") == 2

    assert _parse_bool_env("") is False
    assert _parse_bool_env("1") is True
    assert _parse_bool_env("0") is False
    assert _parse_bool_env("wat") is False


def test_call_by_memoize_field_cache_unhashable_and_double_disable(caplog: pytest.LogCaptureFixture) -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import (
        CallByMemoizationController,
        CallByMemoizationFieldCache,
        CallByMemoizeFieldFilter,
    )

    cache = CallByMemoizationFieldCache("f0", max_entries=4)
    hit, _value, hashable = cache.try_get({"k": "v"})
    assert hit is False
    assert hashable is False
    assert cache.unhashable == 1

    cache._disable("x")
    cache._disable("y")
    assert cache.disabled_reason == "x"
    assert cache.disabled == 1

    cache_zero = CallByMemoizationFieldCache("f0", max_entries=0)
    cache_zero.store_miss(key="k", value=1)
    assert cache_zero.unique_inserts == 0

    controller = CallByMemoizationController(
        max_entries=4,
        field_filter=CallByMemoizeFieldFilter(allow_patterns=(), deny_patterns=()),
        log_stats=True,
    )
    caplog.set_level("INFO", logger="scalim.performance")
    controller.maybe_log_summary()
    assert not caplog.records


def test_call_by_memoize_summary_counts_disabled_fields() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import CallByMemoizationController, CallByMemoizeFieldFilter

    controller = CallByMemoizationController(
        max_entries=4,
        field_filter=CallByMemoizeFieldFilter(allow_patterns=(), deny_patterns=()),
        log_stats=False,
    )
    cache = controller.get_or_create_field_cache("f0")
    cache._disable("x")
    summary = controller.build_summary(top_n=0)
    assert summary["totals"]["disabled_fields"] == 1


def test_call_by_memoize_field_cache_maybe_disable_keeps_high_hit_rate_cache_enabled() -> None:
    from scalim.execution.executor.runtime._internal.call_by_memoization import CallByMemoizationFieldCache

    cache = CallByMemoizationFieldCache("f0", max_entries=2)

    # Ensure `hits+misses` reaches the disable window, while keeping hit rate high.
    for _ in range(8):
        hit, _value, hashable = cache.try_get("k0")
        assert hashable is True
        if not hit:
            cache.store_miss(key="k0", value=1)

    # Trigger at least one eviction; should not disable due to high hit rate.
    cache.store_miss(key="k1", value=1)
    cache.store_miss(key="k2", value=1)

    assert cache.evictions > 0
    assert cache.disabled_reason is None
