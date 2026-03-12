import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Runtime Guardrails 演示 - RowLike + quiet/fast_fail

    本 demo 专注验证两件事:

    1. **RowLike 字段提取契约**(避免静默 None):
       - Mapping.get > 属性访问 > `__getitem__`
       - 覆盖 `dict` / `UserDict` / `MappingProxyType` / `SimpleNamespace` / dataclass / duck-typed `__getitem__`

    2. **Guardrails 行为**:
       - `mode=quiet`: 违规写 None + 通过 ErrorEvent 记录,但不中止
       - `mode=fast_fail`: 首次违规即抛 `GuardrailViolation`

    另外包含 **对拍验证**: 输出 rows 与预期完全一致.
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys as _sys
    from pathlib import Path as _Path

    _this_dir = _Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _guardrails_demo_loaders import load_guardrails_demo_main_rows, load_guardrails_demo_ref_table

    from scalim.events.catalog import EVENT_ERROR
    from scalim.execution import ScalimEngine
    from scalim.execution.guardrails import GuardrailsLoaderPolicy, GuardrailsPolicy, GuardrailViolation
    from scalim.ob.manager import ObserverManager
    from scalim.ob.observer import EventDispatchObserver
    from scalim.planning import PlanBuilder
    from scalim.spec.ir import DemandIr, DerivedFieldIr, FieldIr, KeyIr, LoaderIr, MainSourceIr, SourceIr

    return (
        DemandIr,
        DerivedFieldIr,
        EVENT_ERROR,
        EventDispatchObserver,
        FieldIr,
        GuardrailsLoaderPolicy,
        GuardrailsPolicy,
        GuardrailViolation,
        KeyIr,
        LoaderIr,
        MainSourceIr,
        ObserverManager,
        PlanBuilder,
        ScalimEngine,
        SourceIr,
        load_guardrails_demo_main_rows,
        load_guardrails_demo_ref_table,
    )


@app.cell
def _(
    DemandIr,
    DerivedFieldIr,
    EVENT_ERROR,
    EventDispatchObserver,
    FieldIr,
    KeyIr,
    LoaderIr,
    MainSourceIr,
    SourceIr,
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
):
    class ErrorCollector(EventDispatchObserver):
        event_types = {EVENT_ERROR}

        def __init__(self) -> None:
            self.errors = []

        def on_error(self, payload):  # noqa: ANN001
            self.errors.append(payload)

    def build_demo_demand() -> DemandIr:
        main_source = MainSourceIr(source_id="main", loader=load_guardrails_demo_main_rows)

        ref_source = SourceIr(
            source_id="ref",
            key=KeyIr("id"),
            loader_spec=LoaderIr(callable=load_guardrails_demo_ref_table),
        )

        rel_to_ref = main_source["ref_id"].join(ref_source["id"])

        fields = [
            FieldIr(field_id="ref_id", name="ref_id", source=main_source),
            FieldIr(field_id="a", name="a", source=main_source, transform=int),
            FieldIr(field_id="b", name="b", source=main_source),
            DerivedFieldIr(field_id="ratio", name="ratio", dependencies=("a", "b"), calculator=lambda a, b: a / b),
            FieldIr(field_id="ref_value", name="ref_value", source=ref_source, data_key="value", relation=rel_to_ref),
        ]

        return DemandIr.from_irs(
            sources=[ref_source],
            fields=fields,
            main_source=main_source,
            name="runtime_guardrails_demo",
            batch_size_hint=50,
        )

    def assert_rows_equal(actual, expected):  # noqa: ANN001
        if actual != expected:
            msg = "Output mismatch!\nactual={!r}\nexpected={!r}".format(actual, expected)
            raise AssertionError(msg)

    return ErrorCollector, assert_rows_equal, build_demo_demand


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## quiet 模式: 对拍 + 记录违规
    """)
    return


@app.cell
def _(
    GuardrailsLoaderPolicy,
    GuardrailsPolicy,
    ObserverManager,
    PlanBuilder,
    ScalimEngine,
    ErrorCollector,
    assert_rows_equal,
    build_demo_demand,
):
    demand = build_demo_demand()
    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    plan = PlanBuilder(demand).build(targets=targets)

    guardrails_quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    error_collector = ErrorCollector()
    observer_manager = ObserverManager(observers=[error_collector])

    engine = ScalimEngine(demand=demand, plan=plan, observer_manager=observer_manager, batch_size=50, guardrails=guardrails_quiet)
    rows = engine.run()

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
    assert_rows_equal(rows, expected_rows)

    guardrail_errors = [e for e in error_collector.errors if getattr(e, "context", {}).get("guardrail")]
    codes = sorted({e.context.get("guardrail_code") for e in guardrail_errors})
    assert "loader_transform_error" in codes
    assert "compute_error" in codes
    assert "loader_required_field_missing" in codes

    print("✅ `quiet`: 行数据一致; 已记录护栏代码: {}".format(", ".join(codes)))
    return codes, demand, plan, rows


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""---
    ## fast_fail 模式: 首次违规即终止
    """)
    return


@app.cell
def _(GuardrailsLoaderPolicy, GuardrailsPolicy, GuardrailViolation, ScalimEngine, demand, plan):
    guardrails_fast_fail = GuardrailsPolicy(enabled=True, mode="fast_fail", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    engine_fast = ScalimEngine(demand=demand, plan=plan, batch_size=50, guardrails=guardrails_fast_fail)
    try:
        _ = engine_fast.run()
    except GuardrailViolation as e:
        assert e.code == "loader_transform_error"
        print("✅ `fast_fail`: 抛出 {} (错误码={})".format(type(e).__name__, e.code))
    else:
        raise AssertionError("预期 `fast_fail` 模式应抛出 GuardrailViolation")
    return


if __name__ == "__main__":
    app.run()
