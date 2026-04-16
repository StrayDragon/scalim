from types import SimpleNamespace
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
from scalim.dsl.yaml_dsl._internal.workflow_injected_entrypoints import run_workflow_injected
from scalim.dsl.yaml_dsl.runtime.contracts import UNSET
from scalim.dsl.yaml_dsl.runtime.entrypoints import run as run_demand
from scalim.dsl.yaml_dsl.workflow_types import WorkflowNodePatch, WorkflowRunOptions
from scalim.execution.run_ir import run_ir as run_ir_real
from scalim.events import EVENT_PRE_USE_BATCH_SIZE
from scalim.hooks import BaseHook, HookManager, PreUseBatchSizeDecision


_ALLOWED_MODULES = frozenset({"tests.fixtures.yaml_outputs_e2e"})


def _write_demand_yaml(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(
        (
            """
name: demo
main_source:
  source_id: orders
  loader: "tests.fixtures.yaml_outputs_e2e:demo_orders_loader"
  fields:
    order_id:
      extract: order_id
sources: {}
"""
        ).lstrip(),
        encoding="utf-8",
    )
    return path


def _write_workflow_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "workflow.yaml"
    path.write_text(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
    - id: b
      demand: b.yaml
      init_vars:
        node_key: "node_b"
"""
        ).lstrip(),
        encoding="utf-8",
    )
    return path


class _NoOpHook(BaseHook):
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    def on_pre_use_batch_size(self, decision: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
        self.calls += 1


class _OverrideHookA(BaseHook):
    last_decision: Optional[Any]

    def __init__(self) -> None:
        self.last_decision = None

    def on_pre_use_batch_size(self, decision: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
        self.last_decision = decision
        decision.override(8000, reason="A")  # pragma: allow-dynattr decision override contract


class _OverrideHookB(BaseHook):
    last_decision: Optional[Any]

    def __init__(self) -> None:
        self.last_decision = None

    def on_pre_use_batch_size(self, decision: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
        self.last_decision = decision
        decision.override(10000, reason="B")  # pragma: allow-dynattr decision override contract


class _ExplodingHook(BaseHook):
    def on_pre_use_batch_size(self, decision: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
        _ = decision
        raise RuntimeError("boom")


def test_pre_use_batch_size_signal_skipped_when_explicit_batch_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")
    hook = _ExplodingHook()
    captured: Dict[str, Any] = {}

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        captured["request"] = request
        return SimpleNamespace(output_path=None, total_rows=0, duration=0.0, demand_ir=demand_ir, plan=None, outputs=None)

    import scalim.dsl.yaml_dsl.runtime.entrypoints as entrypoints_mod

    monkeypatch.setattr(entrypoints_mod, "run_ir", _run_ir_stub)

    # Explicit value => MUST skip signal, so exploding hook must not run.
    result = run_demand(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            runtime=DemandRunRuntimeOptions(batch_size=8000, components=[hook]),
        ),
    )
    assert result is not None
    assert int(captured["request"].batch_size) == 8000


def test_pre_use_batch_size_signal_override_takes_effect_when_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")
    hook_a = _OverrideHookA()
    hook_b = _OverrideHookB()
    captured: Dict[str, Any] = {}

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        captured["request"] = request
        return SimpleNamespace(output_path=None, total_rows=0, duration=0.0, demand_ir=demand_ir, plan=None, outputs=None)

    import scalim.dsl.yaml_dsl.runtime.entrypoints as entrypoints_mod

    monkeypatch.setattr(entrypoints_mod, "run_ir", _run_ir_stub)

    _ = run_demand(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            runtime=DemandRunRuntimeOptions(components=[hook_a, hook_b]),
        ),
    )
    assert int(captured["request"].batch_size) == 10000
    assert hook_a.last_decision is not None
    assert hook_b.last_decision is not None
    assert hook_a.last_decision is hook_b.last_decision
    history = list(hook_a.last_decision.history)  # pragma: allow-dynattr decision history contract
    assert [item.hook_id for item in history] == ["_OverrideHookA", "_OverrideHookB"]
    assert [item.reason for item in history] == ["A", "B"]
    assert [(item.prev_value, item.next_value) for item in history] == [(1000, 8000), (8000, 10000)]


def test_pre_use_batch_size_signal_is_fail_fast_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")
    hook = _ExplodingHook()

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        _ = demand_ir
        _ = request
        raise AssertionError("run_ir must not be called when policy hook fails")

    import scalim.dsl.yaml_dsl.runtime.entrypoints as entrypoints_mod

    monkeypatch.setattr(entrypoints_mod, "run_ir", _run_ir_stub)

    with pytest.raises(RuntimeError, match="boom"):
        _ = run_demand(
            str(yaml_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                runtime=DemandRunRuntimeOptions(components=[hook]),
            ),
        )


def test_explicit_none_skips_signal_and_propagates_to_execution_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")
    hook = _NoOpHook()
    captured: Dict[str, Any] = {}

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        captured["request"] = request
        return SimpleNamespace(output_path=None, total_rows=0, duration=0.0, demand_ir=demand_ir, plan=None, outputs=None)

    import scalim.dsl.yaml_dsl.runtime.entrypoints as entrypoints_mod

    monkeypatch.setattr(entrypoints_mod, "run_ir", _run_ir_stub)

    _ = run_demand(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
            runtime=DemandRunRuntimeOptions(batch_size=None, components=[hook]),
        ),
    )
    assert hook.calls == 0
    assert captured["request"].batch_size is None


def test_run_workflow_per_run_patch_batch_size_skips_signal_and_other_runs_can_override(tmp_path: Path) -> None:
    _ = _write_demand_yaml(tmp_path, "a.yaml")
    _ = _write_demand_yaml(tmp_path, "b.yaml")
    workflow_path = _write_workflow_yaml(tmp_path)

    class _WorkflowHook(BaseHook):
        decisions_by_run_id: Dict[str, Any]

        def __init__(self) -> None:
            self.decisions_by_run_id = {}

        def on_pre_use_batch_size(self, decision: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
            run_id = str(getattr(decision, "run_id", ""))
            self.decisions_by_run_id[run_id] = decision
            decision.override(20000, reason="wf")  # pragma: allow-dynattr decision override contract

    hook = _WorkflowHook()
    captured: Dict[str, int] = {}

    def _run_ir_capture(demand_ir: Any, request: Any, *_args: Any, **kwargs: Any) -> Any:
        meta = kwargs.get("event_meta_defaults") or {}
        node_id = str(meta.get("workflow_node_id", ""))
        captured[node_id] = request.batch_size
        return run_ir_real(demand_ir, request, *_args, **kwargs)

    demand_options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
        template=DemandRunTemplateOptions(init_vars={"base_key": "base"}),
        runtime=DemandRunRuntimeOptions(batch_size=UNSET, components=[hook]),
    )
    options = WorkflowRunOptions(
        demand=demand_options,
        patches_by_run_id={"a": WorkflowNodePatch(batch_size=5000)},
    )
    result = run_workflow_injected(str(workflow_path), options=options, run_ir_fn=_run_ir_capture)
    assert result is not None

    assert captured["a"] == 5000
    assert captured["b"] == 20000

    assert "a" not in hook.decisions_by_run_id
    decision_b = hook.decisions_by_run_id["b"]
    assert Path(str(getattr(decision_b, "demand_path"))).name == "b.yaml"
    assert dict(getattr(decision_b, "init_vars") or {}) == {"base_key": "base", "node_key": "node_b"}


def test_pre_use_batch_size_decision_override_validates_inputs() -> None:
    decision = PreUseBatchSizeDecision(value=1000)

    with pytest.raises(ValueError, match="reason"):
        decision.override(2000, reason="")

    with pytest.raises(TypeError, match="batch_size"):
        decision.override(True, reason="bad-type")

    with pytest.raises(ValueError, match=">= 1"):
        decision.override(0, reason="bad-value")

    decision.override(None, reason="no-chunking")
    assert decision.value is None
    assert decision.history[-1].hook_id == "<unknown>"
    assert decision.history[-1].prev_value == 1000
    assert decision.history[-1].next_value is None


def test_emit_pre_use_batch_size_signal_works_without_enter_exit_contract() -> None:
    hook = _NoOpHook()

    payload = SimpleNamespace(value=1000)
    manager = HookManager()
    manager.register(hook)
    manager.emit_typed_policy(EVENT_PRE_USE_BATCH_SIZE, payload)

    assert hook.calls == 1


def test_unsafe_run_emits_pre_use_batch_size_signal_and_updates_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")

    class _Hook(BaseHook):
        def on_pre_use_batch_size(self, payload: Any) -> None:  # pragma: allow-dynattr typed hook signal contract
            payload.override(12345, reason="unsafe")  # pragma: allow-dynattr decision override contract

    captured: Dict[str, Any] = {}

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        captured["request"] = request
        return SimpleNamespace(output_path=None, total_rows=0, duration=0.0, demand_ir=demand_ir, plan=None, outputs=None)

    import scalim.dsl.yaml_dsl.runtime.unsafe_entrypoints as unsafe_mod

    monkeypatch.setattr(unsafe_mod, "run_ir", _run_ir_stub)

    _ = unsafe_mod.unsafe_run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        components=[_Hook()],
    )
    assert int(captured["request"].batch_size) == 12345


def test_unsafe_run_skips_pre_use_batch_size_signal_when_batch_size_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_path = _write_demand_yaml(tmp_path, "demand.yaml")

    hook = _ExplodingHook()
    captured: Dict[str, Any] = {}

    def _run_ir_stub(demand_ir: Any, request: Any, *_args: Any, **_kwargs: Any) -> Any:
        captured["request"] = request
        return SimpleNamespace(output_path=None, total_rows=0, duration=0.0, demand_ir=demand_ir, plan=None, outputs=None)

    import scalim.dsl.yaml_dsl.runtime.unsafe_entrypoints as unsafe_mod

    monkeypatch.setattr(unsafe_mod, "run_ir", _run_ir_stub)

    _ = unsafe_mod.unsafe_run(
        str(yaml_path),
        allowed_modules=_ALLOWED_MODULES,
        batch_size=4321,
        components=[hook],
    )
    assert int(captured["request"].batch_size) == 4321
