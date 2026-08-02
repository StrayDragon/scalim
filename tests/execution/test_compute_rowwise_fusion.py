"""c20 row-wise fusion: 值 / calc_calls / 安全外壳."""

from typing import Any, Dict, List, Optional

import pytest

from scalim.execution.engine import ScalimEngine
from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import BaseHook, HookManager
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryColumnSink, InMemoryRowDataSink
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr


def _call_by(fid: str, deps: List[str]) -> CallBySpecIr:
    return CallBySpecIr(
        reference=RuntimeHandleIdIr(handle_id="{}.calculator".format(fid)),
        args=tuple(CallByValueIr(kind="field", value=d) for d in deps),
        field_names=tuple(deps),
    )


def _build_demand(n_derived: int = 3):
    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))
    fields: List[Any] = [
        FieldIr(field_id="id", name="id", source=main, is_primary=True),
        FieldIr(field_id="v0", name="v0", source=main),
        FieldIr(field_id="v1", name="v1", source=main),
    ]
    targets = ["id", "v0", "v1"]
    for i in range(n_derived):
        fid = "d{}".format(i)
        fields.append(
            DerivedFieldIr(
                field_id=fid,
                name=fid,
                dependencies=("v0", "v1"),
                call_by=_call_by(fid, ["v0", "v1"]),
            )
        )
        targets.append(fid)
    demand = DemandIr.from_irs(sources=[], fields=fields, main_source=main)
    return demand, targets


class _FieldComputeHook(BaseHook):
    def __init__(self) -> None:
        self.count = 0

    def on_field_compute(self, event) -> None:  # type: ignore[override]
        self.count += 1


def _run_row(
    *,
    n_rows: int = 20,
    n_derived: int = 3,
    force_no_fusion: bool = False,
    guardrails: Optional[GuardrailsPolicy] = None,
    column: bool = False,
    hook_manager: Optional[HookManager] = None,
) -> Dict[str, Any]:
    demand, targets = _build_demand(n_derived)
    plan = PlanBuilder(demand).build(targets=targets)
    # 强制走 compute 段(否则 write-only 派生会进 late,测不到 c20 融合).
    plan.late_fields = ()
    if force_no_fusion:
        plan.compute_fusion_groups = ()

    calc_calls = {"n": 0}
    calcs = {}

    def _make(i: int):
        def _calc(a: Any, b: Any) -> Any:
            calc_calls["n"] += 1
            return float(a or 0) + float(b or 0) + float(i)

        return _calc

    for i in range(n_derived):
        calcs["d{}".format(i)] = _make(i)

    bindings = RuntimeBindings(derived_calculators=calcs)
    data = [{"id": i, "v0": float(i), "v1": float(i % 7)} for i in range(n_rows)]
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=bindings,
        parallel_mode="seq",
        batch_size=n_rows,
        guardrails=guardrails or GuardrailsPolicy.disabled(),
        hook_manager=hook_manager,
    )

    if column:
        with InMemoryColumnSink(field_names=targets) as sink:
            engine.run(main_rows=data, sink=sink)
            rows = list(sink.get_rows())
    else:
        with InMemoryRowDataSink() as sink:
            engine.run(main_rows=data, sink=sink)
            rows = list(sink.get_data())

    return {
        "rows": rows,
        "calc_calls": calc_calls["n"],
        "fusion_groups": plan.compute_fusion_groups,
        "n_derived": n_derived,
        "n_rows": n_rows,
    }


def test_fusion_values_and_calc_calls_match_field_major() -> None:
    fused = _run_row(force_no_fusion=False)
    major = _run_row(force_no_fusion=True)

    assert fused["fusion_groups"]
    assert fused["calc_calls"] == major["calc_calls"]
    assert fused["calc_calls"] == fused["n_rows"] * fused["n_derived"]
    assert fused["rows"] == major["rows"]


def test_column_sink_does_not_require_fusion_for_correctness() -> None:
    out = _run_row(column=True)
    assert out["calc_calls"] == out["n_rows"] * out["n_derived"]
    for i, row in enumerate(out["rows"]):
        assert float(row["d0"]) == float(i) + float(i % 7) + 0.0


def test_fast_fail_guardrails_still_correct() -> None:
    out = _run_row(guardrails=GuardrailsPolicy(enabled=True, mode="fast_fail"))
    assert out["calc_calls"] == out["n_rows"] * out["n_derived"]


def test_field_compute_subscription_disables_fusion_but_keeps_values() -> None:
    hook = _FieldComputeHook()
    hub = HookManager()
    hub.register(hook)
    fused_path = _run_row(hook_manager=hub)
    major = _run_row(force_no_fusion=True)
    assert fused_path["rows"] == major["rows"]
    assert fused_path["calc_calls"] == major["calc_calls"]
    assert hook.count == fused_path["n_rows"] * fused_path["n_derived"]


def test_fused_values_survive_batch_result_extraction() -> None:
    """融合写出必须同步维护稠密 `present_count`,否则行释放会把整列当成空存储回收."""
    demand, targets = _build_demand(3)
    plan = PlanBuilder(demand).build(targets=targets)
    plan.late_fields = ()
    assert plan.compute_fusion_groups

    calcs = {"d{}".format(i): (lambda a, b, i=i: float(a or 0) + float(b or 0) + float(i)) for i in range(3)}
    data = [{"id": i, "v0": float(i), "v1": float(i % 7)} for i in range(4)]
    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=RuntimeBindings(derived_calculators=calcs),
        parallel_mode="seq",
        batch_size=4,
        guardrails=GuardrailsPolicy.disabled(),
    )

    rows = list(engine.run(main_rows=data))

    assert [row["d0"] for row in rows] == [float(i) + float(i % 7) for i in range(4)]
    assert [row["d2"] for row in rows] == [float(i) + float(i % 7) + 2.0 for i in range(4)]


def test_exp_memo_disables_whole_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from scalim.execution.executor.operators.compute.fusion import fusion_disabled_reason
    from scalim.planning.builder_helpers.fusion_groups import ComputeFusionGroup

    from tests.fixtures.executor_operator_fixtures import _make_runtime

    monkeypatch.setenv("SCALIM_EXP_CALL_BY_MEMOIZE_MAX_ENTRIES", "64")
    demand, targets = _build_demand(3)
    plan = PlanBuilder(demand).build(targets=targets)
    plan.late_fields = ()
    calcs = {"d{}".format(i): (lambda a, b, i=i: float(a or 0) + float(b or 0) + float(i)) for i in range(3)}
    bindings = RuntimeBindings(derived_calculators=calcs)
    runtime = _make_runtime(plan, None, runtime_bindings=bindings)
    group = plan.compute_fusion_groups[0]
    assert isinstance(group, ComputeFusionGroup)
    assert fusion_disabled_reason(runtime, group, group.field_keys) == "memo"
    out = _run_row(n_rows=8, n_derived=3)
    assert len(out["rows"]) == 8
    assert out["calc_calls"] > 0
