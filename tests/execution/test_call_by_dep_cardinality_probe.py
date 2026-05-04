import pytest


def test_call_by_dep_cardinality_collector_reports_repeat_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.runtime._internal.call_by_dep_cardinality import build_call_by_dep_cardinality_collector

    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")
    collector = build_call_by_dep_cardinality_collector()
    assert collector is not None

    collector.record(field_key="f0", dep_args=(1, 2))
    collector.record(field_key="f0", dep_args=(1, 2))
    collector.record(field_key="f0", dep_args=(2, 3))

    summary = collector.build_summary(top_n=10)
    assert summary["enabled"] is True
    assert summary["max_unique"] == 16
    assert len(summary["fields"]) == 1

    field = summary["fields"][0]
    assert field["field_key"] == "f0"
    assert field["call_count"] == 3
    assert field["hashable_count"] == 3
    assert field["unique_hashes"] == 2
    assert field["unique_overflow"] is False
    assert field["repeat_rate"] == pytest.approx(1.0 - 2.0 / 3.0, rel=0, abs=1e-6)

    # `top_n <= 0` should keep all fields.
    summary2 = collector.build_summary(top_n=0)
    assert len(summary2["fields"]) == 1


def test_call_by_dep_cardinality_collector_records_unhashable_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.runtime._internal.call_by_dep_cardinality import build_call_by_dep_cardinality_collector

    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "16")
    collector = build_call_by_dep_cardinality_collector()
    assert collector is not None

    collector.record(field_key="f0", dep_args=({"k": "v"},))
    summary = collector.build_summary(top_n=10)
    field = summary["fields"][0]
    assert field["call_count"] == 1
    assert field["hashable_count"] == 0
    assert field["unhashable_count"] == 1


def test_call_by_dep_cardinality_collector_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.runtime._internal.call_by_dep_cardinality import build_call_by_dep_cardinality_collector

    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "1")
    collector = build_call_by_dep_cardinality_collector()
    assert collector is not None

    collector.record(field_key="f0", dep_args=(1,))
    collector.record(field_key="f0", dep_args=(2,))
    collector.record(field_key="f0", dep_args=(3,))

    summary = collector.build_summary(top_n=10)
    field = summary["fields"][0]
    assert field["unique_overflow"] is True
    assert field["unique_hashes"] == 1


def test_build_call_by_dep_cardinality_collector_handles_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.runtime._internal.call_by_dep_cardinality import build_call_by_dep_cardinality_collector

    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "not-an-int")
    collector = build_call_by_dep_cardinality_collector()
    assert collector is not None
    assert collector.max_unique == 8192


def test_build_call_by_dep_cardinality_collector_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.runtime._internal.call_by_dep_cardinality import build_call_by_dep_cardinality_collector

    monkeypatch.setenv("SCALIM_PROBE_CALL_BY_DEP_CARDINALITY", "0")
    assert build_call_by_dep_cardinality_collector() is None
