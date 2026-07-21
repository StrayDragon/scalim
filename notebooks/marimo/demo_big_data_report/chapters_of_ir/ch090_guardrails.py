"""Cells-native: ch090_guardrails — runtime guardrails quiet/fast_fail modes."""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Runtime Guardrails: quiet vs fast_fail

演示 GuardrailsPolicy quiet 模式（记录违规 + 对拍）和 fast_fail 模式（首次违规即抛出）。""")
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    ensure_repo_root_on_sys_path(__file__)
    return


@app.cell
def _():
    from typing import Any, Dict, List, Sequence

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

    return (
        Any,
        BindingIr,
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        Dict,
        EventDispatchObserver,
        EventType,
        FieldIr,
        GuardrailsLoaderPolicy,
        GuardrailsPolicy,
        KeyIr,
        List,
        LoaderIr,
        MainSourceIr,
        ObserverManager,
        PlanBuilder,
        RuntimeBindings,
        RuntimeHandleIdIr,
        ScalimEngine,
        ScalimGuardrailViolationError,
        Sequence,
        SourceIr,
        ValueOpIr,
        load_guardrails_demo_main_rows,
        load_guardrails_demo_ref_table,
    )


@app.cell
def _(
    BindingIr,
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    EventDispatchObserver,
    EventType,
    FieldIr,
    KeyIr,
    List,
    LoaderIr,
    MainSourceIr,
    RuntimeBindings,
    RuntimeHandleIdIr,
    SourceIr,
    ValueOpIr,
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
):
    """Build IR demand and runtime bindings."""

    def to_int(value):
        return int(value)

    main_source = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.main_loader"))
    ref_source = SourceIr(
        source_id="ref",
        key=KeyIr("id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="ref.loader"),
            bindings={"id": BindingIr(key_field="id", params_builder_ref=RuntimeHandleIdIr(handle_id="ref.params_builder.id"))},
        ),
    )
    rel_to_ref = main_source["ref_id"].join(ref_source["id"])

    fields = [
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
                args=(CallByValueIr(kind="field", value="a"), CallByValueIr(kind="field", value="b")),
                field_names=("a", "b"),
            ),
        ),
        FieldIr(field_id="ref_value", name="ref_value", source=ref_source, data_key="value", relation=rel_to_ref),
    ]

    demand = DemandIr.from_irs(
        sources=[ref_source], fields=fields, main_source=main_source, name="runtime_guardrails_demo", batch_size_hint=50
    )

    runtime = RuntimeBindings()
    runtime.main_source_loaders["main"] = load_guardrails_demo_main_rows
    runtime.source_loaders["ref"] = load_guardrails_demo_ref_table

    def params_fn(ctx):
        ids = ctx.lookup_keys_list or []
        return (), {"ids": ids}

    runtime.params_builders[("ref", "id")] = params_fn
    runtime.value_transforms["a"] = to_int
    runtime.derived_calculators["ratio"] = lambda a, b: a / b

    class ErrorCollector(EventDispatchObserver):
        def __init__(self):
            self.event_types = {EventType.ERROR}
            self.errors = []

        def on_error(self, payload):
            self.errors.append(payload)

    return ErrorCollector, demand, runtime, to_int


@app.cell
def _(
    ErrorCollector,
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    ObserverManager,
    PlanBuilder,
    ScalimEngine,
    demand,
    runtime,
):
    """Quiet mode: collects guardrail violations without aborting."""
    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    plan = PlanBuilder(demand).build(targets=targets)

    guardrails_quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    error_collector = ErrorCollector()
    om = ObserverManager(observers=[error_collector])

    engine = ScalimEngine(
        demand=demand, plan=plan, runtime_bindings=runtime, observer_manager=om, batch_size=50, guardrails=guardrails_quiet
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
    print("quiet: rows_ok={} codes_ok={} codes={}".format(quiet_rows_ok, codes_ok, codes))
    return codes, codes_ok, error_collector, quiet_rows_ok


@app.cell
def _(
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    PlanBuilder,
    ScalimEngine,
    ScalimGuardrailViolationError,
    demand,
    runtime,
):
    """Fast-fail mode: build fresh plan and verify exception."""
    plan2 = PlanBuilder(demand).build(targets=["ref_id", "a", "b", "ratio", "ref_value"])
    guardrails_ff = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    engine_ff = ScalimEngine(demand=demand, plan=plan2, runtime_bindings=runtime, batch_size=50, guardrails=guardrails_ff)
    fast_fail_ok = False
    try:
        engine_ff.run()
    except ScalimGuardrailViolationError as exc:
        fast_fail_ok = exc.code == "loader_transform_error"
    print("fast_fail_ok={}".format(fast_fail_ok))
    return fast_fail_ok, plan2


@app.cell
def _(codes, codes_ok, fast_fail_ok, quiet_rows_ok):
    passed = bool(quiet_rows_ok and codes_ok and fast_fail_ok)
    summary = "quiet_rows_ok={} guardrail_codes_ok={} fast_fail_ok={}".format(quiet_rows_ok, codes_ok, fast_fail_ok)
    chapter_result = {"passed": passed, "summary": summary, "details": {"codes": codes}}
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
