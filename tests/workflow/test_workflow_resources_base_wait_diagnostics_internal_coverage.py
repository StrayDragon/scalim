import math

import pytest

from scalim.workflow.resources_base import WorkflowResourceWaitDiagnostics


def test_wait_diagnostics_disabled_helper_is_stable() -> None:
    d = WorkflowResourceWaitDiagnostics.disabled()
    assert d.enabled is False
    assert d.warn_after_s == 30.0
    assert d.repeat_every_s is None
    assert d.capture_owner_callsite is False


def test_wait_diagnostics_normalizes_values() -> None:
    d = WorkflowResourceWaitDiagnostics(enabled=1, warn_after_s="0.1", repeat_every_s="0.2", capture_owner_callsite=1)  # type: ignore[arg-type]
    assert d.enabled is True
    assert d.warn_after_s == 0.1
    assert d.repeat_every_s == 0.2
    assert d.capture_owner_callsite is True


@pytest.mark.parametrize("raw", [-1.0, float("inf"), float("nan")])
def test_wait_diagnostics_rejects_invalid_warn_after(raw: float) -> None:
    with pytest.raises(ValueError, match=r"warn_after_s must be a finite non-negative float"):
        _ = WorkflowResourceWaitDiagnostics(enabled=True, warn_after_s=raw)


@pytest.mark.parametrize("raw", [-1.0, 0.0, float("inf"), float("nan")])
def test_wait_diagnostics_rejects_invalid_repeat_every(raw: float) -> None:
    warn_after = 0.1 if math.isfinite(raw) else 0.1
    with pytest.raises(ValueError, match=r"repeat_every_s must be a finite positive float"):
        _ = WorkflowResourceWaitDiagnostics(enabled=True, warn_after_s=warn_after, repeat_every_s=raw)
