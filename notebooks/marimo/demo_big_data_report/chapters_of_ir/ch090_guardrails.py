import marimo

from typing import Any, Dict, List, Optional, Sequence

from scalim.events import EventType
from scalim.execution.engine import ScalimEngine
from scalim.execution.guardrails import GuardrailsLoaderPolicy, GuardrailsPolicy, ScalimGuardrailViolationError
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver
from scalim.planning import PlanBuilder
from scalim.spec.ir import (
    BindingIr,
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    KeyIr,
    LoaderIr,
    MainSourceIr,
    RuntimeHandleIdIr,
    SourceIr,
    ValueOpIr,
)
from scalim_misc.demo_big_data_report.guardrails_demo_loaders import (
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
)
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")


def _to_int(value: Any) -> int:
    return int(value)


class _ErrorCollector(EventDispatchObserver):
    def __init__(self) -> None:
        self.event_types = {EventType.ERROR}
        self.errors: List[Any] = []

    def on_error(self, payload: Any) -> None:
        self.errors.append(payload)


def _build_demand() -> DemandIr:
    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.main_loader"))
    ref_source = SourceIr(
        source_id="ref",
        key=KeyIr("id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="ref.loader"),
            bindings={
                "id": BindingIr(
                    key_field="id",
                    params_builder_ref=RuntimeHandleIdIr(handle_id="ref.params_builder.id"),
                )
            },
        ),
    )
    rel_to_ref = main_source["ref_id"].join(ref_source["id"])

    fields: Sequence[Any] = [
        FieldIr(field_id="ref_id", name="ref_id", source=main_source),
        FieldIr(
            field_id="a",
            name="a",
            source=main_source,
            value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="field.a.transform")),),
        ),
        FieldIr(field_id="b", name="b", source=main_source),
        DerivedFieldIr(
            field_id="ratio",
            name="ratio",
            dependencies=("a", "b"),
            call_by=CallBySpecIr(
                reference=RuntimeHandleIdIr(handle_id="derived.ratio"),
                args=(
                    CallByValueIr(kind="field", value="a"),
                    CallByValueIr(kind="field", value="b"),
                ),
                field_names=("a", "b"),
            ),
        ),
        FieldIr(field_id="ref_value", name="ref_value", source=ref_source, data_key="value", relation=rel_to_ref),
    ]

    return DemandIr.from_irs(
        sources=[ref_source],
        fields=list(fields),
        main_source=main_source,
        name="runtime_guardrails_demo",
        batch_size_hint=50,
    )


def _build_runtime_bindings() -> RuntimeBindings:
    bindings = RuntimeBindings()
    bindings.main_source_loaders["main"] = load_guardrails_demo_main_rows
    bindings.source_loaders["ref"] = load_guardrails_demo_ref_table

    def _params(ctx) -> Any:
        ids = ctx.lookup_keys_list or []
        return (), {"ids": ids}

    bindings.params_builders[("ref", "id")] = _params

    bindings.value_transforms["a"] = _to_int
    bindings.derived_calculators["ratio"] = lambda a, b: a / b
    return bindings


def run_guardrails() -> ExampleResult:
    demand = _build_demand()
    runtime_bindings = _build_runtime_bindings()
    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    plan = PlanBuilder(demand).build(targets=targets)

    # `quiet`: 记录违规但不中止 + 对拍
    guardrails_quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    error_collector = _ErrorCollector()
    observer_manager = ObserverManager(observers=[error_collector])

    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        observer_manager=observer_manager,
        batch_size=50,
        guardrails=guardrails_quiet,
    )
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
    engine_fast = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=50, guardrails=guardrails_fast_fail)
    fast_fail_ok = False
    try:
        _ = engine_fast.run()
    except ScalimGuardrailViolationError as exc:
        fast_fail_ok = exc.code == "loader_transform_error"

    passed = bool(quiet_rows_ok and codes_ok and fast_fail_ok)
    summary = "quiet_rows_ok={} guardrail_codes_ok={} fast_fail_ok={}".format(quiet_rows_ok, codes_ok, fast_fail_ok)
    details: Dict[str, Any] = {"codes": codes, "rows": rows}
    return ExampleResult(
        example_id="demo_big_data_report/ch090_guardrails",
        passed=passed,
        kind=EXAMPLE_KIND_ORACLE,
        summary=summary,
        details=details,
    )


def run_chapter() -> ExampleResult:
    return run_guardrails()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch090_guardrails

        本章目标:
        - 演示 runtime guardrails 的 quiet 模式与可对拍边界

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_ir/ch090_guardrails.py::run_guardrails`

        Gate:
        - `just examples`（跑全量）
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    return (repo_root,)


@app.cell
def _():
    result = run_guardrails()
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
