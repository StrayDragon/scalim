"""Cells-native: ch090_guardrails — runtime guardrails quiet/fast_fail modes.

设计目标（对齐 repo 金标准 `example_readme_suite/ch010_min_python`）:
- 本章**内联**构造一个最小 IR(主源 main + 引用源 ref + 派生字段 ratio),读者打开即可观察装配。
- 主线装配 `IR → Plan → Engine(两种 guardrails 模式) → 对拍` 全部在 cells 内**逐 cell 展开**。
- 通过 `chapter_result` 向 headless runner / pytest 暴露对拍结果（含 r1114 `expected` 快照）。
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch090_guardrails

        本章演示运行时 **GuardrailsPolicy** 的两种模式:
        - `quiet`(默认):记录违规事件,不中断执行,可对拍输出
        - `fast_fail`:首次违规即抛出 `ScalimGuardrailViolationError`(编译期/运行期快速失败)

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. **内联装配** `DemandIr`:主源 main + 引用源 ref + 派生字段 `ratio`(a/b)
        2. `RuntimeBindings`:注入 loader / params_builder / value_transform / derived_calculator
        3. **(模型窥视)** 渲染 `demand.fields` / 数据源 / 运行时绑定键
        4. `quiet` 模式:收集违规事件(loader_transform/compute/required_field_missing)并对拍输出
        5. `fast_fail` 模式:新建 plan 触发首次违规异常
        6. `make_chapter_result(passed, summary, details={...})` 产出 `chapter_result`(含 `expected` 快照)

        > 本章不调用库 builder:IR、loader、派生计算函数全部在 cells 内展开。

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
        Gate: `just examples`
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
    _ = repo_root
    return (repo_root,)


@app.cell
def _():
    from typing import Any, Dict, List, Sequence

    from scalim.events import Event, EventType
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
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        Any,
        BindingIr,
        CallBySpecIr,
        CallByValueIr,
        DemandIr,
        DerivedFieldIr,
        Dict,
        Event,
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
        make_chapter_result,
    )


@app.cell
def _(
    BindingIr,
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    KeyIr,
    LoaderIr,
    MainSourceIr,
    RuntimeBindings,
    RuntimeHandleIdIr,
    SourceIr,
    ValueOpIr,
    load_guardrails_demo_main_rows,
    load_guardrails_demo_ref_table,
):
    # ① 内联装配 DemandIr + RuntimeBindings(读者打开即可观察怎么写)
    #    - MainSourceIr(source_id="main"):主源,loader_ref 指向运行时为主源注入的 loader
    #    - SourceIr(source_id="ref"):引用源,带 key + LoaderIr(bindings 描述按 key 取参)
    #    - FieldIr.value_ops:字段级 transform(value_transform);DerivedFieldIr:派生计算
    #    - RuntimeBindings:分门别类注入 loader / params_builder / value_transform / derived_calculator
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
        FieldIr(field_id="ref_id", name="ref_id", source_id=main_source.source_id),
        FieldIr(
            field_id="a",
            name="a",
            source_id=main_source.source_id,
            value_ops=(ValueOpIr(kind="transform", callable_ref=RuntimeHandleIdIr(handle_id="field.a.transform")),),
        ),
        FieldIr(field_id="b", name="b", source_id=main_source.source_id),
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
        FieldIr(field_id="ref_value", name="ref_value", source_id=ref_source.source_id, data_key="value", relation=rel_to_ref),
    ]

    demand = DemandIr.from_irs(
        sources=[ref_source], fields=fields, main_source=main_source, name="runtime_guardrails_demo", batch_size_hint=50
    )

    # RuntimeBindings:把 loader / 计算函数注入到对应注入点
    runtime = RuntimeBindings()
    runtime.main_source_loaders["main"] = load_guardrails_demo_main_rows
    runtime.source_loaders["ref"] = load_guardrails_demo_ref_table

    def params_fn(ctx):
        ids = ctx.lookup_keys_list or []
        return (), {"ids": ids}

    runtime.params_builders[("ref", "id")] = params_fn
    runtime.value_transforms["a"] = to_int
    runtime.derived_calculators["ratio"] = lambda a, b: a / b

    # ErrorCollector: 观察者,监听 ERROR 事件(用于收集 guardrail 违规)
    class ErrorCollector(EventDispatchObserver):
        def __init__(self):
            self.event_types = {EventType.ERROR}
            self.errors = []

        def on_error(self, event: Event) -> None:
            payload = event.payload
            self.errors.append(payload)

    return ErrorCollector, demand, runtime, to_int


@app.cell(hide_code=True)
def _(demand, mo, runtime):
    # ② 模型窥视:把内联装配产物直接渲染出来,读者无需跳转其它文件
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in demand.fields.values()
    ]
    source_summary = [{"source_id": sid} for sid in demand.sources.keys()]
    derived_keys = list(getattr(runtime, "derived_calculators", {}).keys()) or list(runtime.derived_calculators.keys())
    mo.vstack(
        [
            mo.md(
                "**模型窥视（无需跳转外部文件）**:`demand.fields` 为 mappingproxy(键=field_id),遍历用 `.values()`;"
                "`DerivedFieldIr` 可能无 `source_id`,用 `getattr` 兜底。"
            ),
            mo.md("**字段结构(`demand.fields`)**:"),
            mo.ui.table(fields_summary, selection=None),
            mo.md("**数据源(`demand.sources`)**:"),
            mo.ui.table(source_summary, selection=None),
            mo.md("**运行时派生计算器键**: {keys}".format(keys=derived_keys)),
        ]
    )
    return


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
    # ③ quiet 模式:收集 guardrail 违规但不中断执行
    #    - PlanBuilder(demand).build(targets):按目标字段生成计划(含 guardrail 要求的字段)
    #    - GuardrailsPolicy(mode="quiet"):记录违规;loader=GuardrailsLoaderPolicy(required_fields=("b",))
    #    - ErrorCollector:监听 ERROR 事件收集违规 payload
    targets = ["ref_id", "a", "b", "ratio", "ref_value"]
    plan = PlanBuilder(demand).build(targets=targets)

    guardrails_quiet = GuardrailsPolicy(enabled=True, mode="quiet", loader=GuardrailsLoaderPolicy(required_fields=("b",)))
    error_collector = ErrorCollector()
    om = ObserverManager(observers=[error_collector])

    engine = ScalimEngine(
        demand=demand, plan=plan, runtime_bindings=runtime, observer_manager=om, batch_size=50, guardrails=guardrails_quiet
    )
    rows = list(engine.run())

    # 期望输出(教学 payload,直接写在 cells 里;含 b=0 → ratio=None,ref 未命中 → ref_value=None)
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
    # ④ fast_fail 模式:新建 plan,首次违规即抛出异常
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
def _(codes, codes_ok, fast_fail_ok, make_chapter_result, quiet_rows_ok):
    # ⑤ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(quiet_rows_ok and codes_ok and fast_fail_ok)
    summary = "quiet_rows_ok={} guardrail_codes_ok={} fast_fail_ok={}".format(quiet_rows_ok, codes_ok, fast_fail_ok)

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "quiet_rows_ok": bool(quiet_rows_ok),
        "guardrail_codes_ok": bool(codes_ok),
        "fast_fail_ok": bool(fast_fail_ok),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "codes": codes,
            "quiet_rows_ok": quiet_rows_ok,
            "codes_ok": codes_ok,
            "fast_fail_ok": fast_fail_ok,
        },
    )
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
