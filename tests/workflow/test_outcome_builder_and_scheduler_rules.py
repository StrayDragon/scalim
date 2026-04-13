"""Unit tests for pure workflow scheduling / outcome helpers (c45 Phase 1a)."""

import pytest

from scalim.exceptions import REDACTED_ERROR_MESSAGE, ScalimWorkflowError
from scalim.workflow.outcome_builder import (
    build_outcome_from_exception,
    build_outcome_from_result,
    safe_error_message,
    safe_error_type,
)
from scalim.workflow.resources import ScalimWorkflowWriteError
from scalim.workflow.scheduler_rules import can_schedule_more, should_cancel_on_failure


def test_safe_error_type_uses_exception_class_name() -> None:
    assert safe_error_type(ValueError("x")) == "ValueError"


def test_safe_error_message_scalim_error_uses_str() -> None:
    exc = ScalimWorkflowError("boom")
    assert "boom" in safe_error_message(exc)


def test_safe_error_message_non_scalim_redacted_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SCALIM_DEBUG_ERRORS", raising=False)
    assert safe_error_message(RuntimeError("secret")) == str(REDACTED_ERROR_MESSAGE or "")


@pytest.mark.parametrize(
    "policy,failed,out",
    [
        ("all_fail", None, False),
        ("all_fail", object(), True),
        ("best_effort", object(), False),
        ("", None, False),
    ],
)
def test_should_cancel_on_failure(policy, failed, out) -> None:
    assert should_cancel_on_failure(policy, failed) is out


@pytest.mark.parametrize(
    "submitted,max_conc,out",
    [
        (0, 1, True),
        (1, 1, False),
        (0, 4, True),
        (3, 4, True),
        (4, 4, False),
    ],
)
def test_can_schedule_more(submitted, max_conc, out) -> None:
    assert can_schedule_more(submitted, max_conc) is out


def test_build_outcome_from_result_preserves_paths() -> None:
    o = build_outcome_from_result({"k": 1}, run_id="n1", demand_path="d.yaml")
    assert o.run_id == "n1"
    assert o.demand_path == "d.yaml"
    assert o.result == {"k": 1}
    assert o.error is None


def test_build_outcome_from_result_none_payload() -> None:
    o = build_outcome_from_result(None, run_id="w1", demand_path="")
    assert o.run_id == "w1"
    assert o.demand_path == ""
    assert o.result is None
    assert o.error is None


def test_build_outcome_from_exception_basic() -> None:
    exc = RuntimeError("nope")
    o = build_outcome_from_exception(exc, run_id="n2", demand_path="p.yaml")
    assert o.run_id == "n2"
    assert o.demand_path == "p.yaml"
    assert o.result is None
    assert o.error is not None
    assert o.error.exc_type == "RuntimeError"
    assert o.error.message
    assert o.error.diff is None


def test_build_outcome_from_exception_write_error_diff() -> None:
    exc = ScalimWorkflowWriteError("write failed", diff=["a", "b"])
    o = build_outcome_from_exception(exc, run_id="n3", demand_path="")
    assert o.error is not None
    assert o.error.diff == ["a", "b"]
