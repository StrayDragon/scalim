from __future__ import annotations

from typing import Any, Dict, List, Sequence

from scalim.events.catalog import EVENT_ERROR
from scalim.execution import ScalimEngine
from scalim.execution.guardrails import GuardrailsLoaderPolicy, GuardrailsPolicy, GuardrailViolation
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver
from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr, DerivedFieldIr, FieldIr, KeyIr, LoaderIr, MainSourceIr, SourceIr

from notebooks.marimo.examples.demo_big_data_report._guardrails_demo_loaders import (
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
)

from ._types import ChapterResult


class _ErrorCollector(EventDispatchObserver):
    event_types = {EVENT_ERROR}

    def __init__(self) -> None:
        self.errors: List[Any] = []

    def on_error(self, payload: Any) -> None:
        self.errors.append(payload)


def _build_demand() -> DemandIr:
    main_source = MainSourceIr(source_id="main", loader=load_guardrails_demo_main_rows)
    ref_source = SourceIr(source_id="ref", key=KeyIr("id"), loader_spec=LoaderIr(callable=load_guardrails_demo_ref_table))
    rel_to_ref = main_source["ref_id"].join(ref_source["id"])

    fields: Sequence[Any] = [
        FieldIr(field_id="ref_id", name="ref_id", source=main_source),
        FieldIr(field_id="a", name="a", source=main_source, transform=int),
        FieldIr(field_id="b", name="b", source=main_source),
        DerivedFieldIr(field_id="ratio", name="ratio", dependencies=("a", "b"), calculator=lambda a, b: a / b),
        FieldIr(field_id="ref_value", name="ref_value", source=ref_source, data_key="value", relation=rel_to_ref),
    ]

    return DemandIr.from_irs(
        sources=[ref_source],
        fields=list(fields),
        main_source=main_source,
        name="runtime_guardrails_demo",
        batch_size_hint=50,
    )


def run_guardrails() -> ChapterResult:
    demand = _build_demand()
    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    plan = PlanBuilder(demand).build(targets=targets)

    # `quiet`: 记录违规但不中止 + 对拍
    guardrails_quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    error_collector = _ErrorCollector()
    observer_manager = ObserverManager(observers=[error_collector])

    engine = ScalimEngine(demand=demand, plan=plan, observer_manager=observer_manager, batch_size=50, guardrails=guardrails_quiet)
    rows = list(engine.run())

    expected_rows = [
        {"ref_id": 1, "a": 1, "b": 2, "ratio": 0.5, "ref_value": "U1"},
        {"ref_id": 2, "a": 2, "b": 4, "ratio": 0.5, "ref_value": "P2"},
        {"ref_id": 3, "a": 3, "b": 0, "ratio": None, "ref_value": "S3"},
        {"ref_id": 4, "a": 4, "b": 8, "ratio": 0.5, "ref_value": "D4"},
        {"ref_id": 5, "a": 5, "b": 10, "ratio": 0.5, "ref_value": "G5"},
        {"ref_id": 999, "a": 6, "b": 12, "ratio": 0.5, "ref_value": None},
        {"ref_id": 1, "a": None, "b": 14, "ratio": None, "ref_value": "U1"},
        {"ref_id": 2, "a": 7, "b": None, "ratio": None, "ref_value": "P2"},
    ]
    quiet_rows_ok = rows == expected_rows

    guardrail_errors = [err for err in error_collector.errors if getattr(err, "context", {}).get("guardrail")]
    codes = sorted({err.context.get("guardrail_code") for err in guardrail_errors})
    codes_ok = all(code in codes for code in ("loader_transform_error", "compute_error", "loader_required_field_missing"))

    # `fast_fail`: 首次违规即抛异常
    guardrails_fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    engine_fast = ScalimEngine(demand=demand, plan=plan, batch_size=50, guardrails=guardrails_fast_fail)
    fast_fail_ok = False
    try:
        _ = engine_fast.run()
    except GuardrailViolation as exc:
        fast_fail_ok = exc.code == "loader_transform_error"

    passed = bool(quiet_rows_ok and codes_ok and fast_fail_ok)
    summary = "quiet_rows_ok={} guardrail_codes_ok={} fast_fail_ok={}".format(quiet_rows_ok, codes_ok, fast_fail_ok)
    details: Dict[str, Any] = {"codes": codes, "rows": rows}
    return ChapterResult(chapter_id="guardrails", passed=passed, summary=summary, details=details)
