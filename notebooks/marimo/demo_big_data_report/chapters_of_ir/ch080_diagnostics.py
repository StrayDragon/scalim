"""Cells-native: ch080_diagnostics — static IR diagnostics (no engine run).

设计目标（对齐 repo 金标准 `chapters_of_ir/ch010_basics`）:
- 本章复用 `build_ecommerce_model` 作为**复杂复用零件**,但**不执行引擎**,仅对 IR 做静态诊断。
- 主线(模型构建 → 模型窥视 → 静态诊断统计)全部在 cells 内**逐 cell 展开**,并渲染装配产物。
- 通过 `chapter_result` 向 headless runner / pytest 暴露对拍结果（含 r1114 `expected` 快照）。
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch080_diagnostics

        本章对 **IR model 做静态诊断**(不运行引擎):统计 fields / relations / derived / cached。

        > 沿用完整电商模型(复杂复用零件),但把主线**摊开在 cells 里**观察"怎么写"。

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. `build_test_config_small()` 构建测试配置 + `build_ecommerce_model(cfg)` 构建 `DemandIr`
        2. **(模型窥视)** 用 `mo.ui.table` 渲染字段结构 / 数据源 / 派生字段 / 缓存源
        3. 静态诊断:按 `FieldIr`/`DerivedFieldIr` 分类,解析 `JoinConditionIr`/`RelationIr` 关联表达式
        4. `make_chapter_result(passed, summary, details={...})` 产出 `chapter_result`(含 `expected` 快照)

        > 本章不执行 `ScalimEngine`,仅对 IR 模型做静态检查;关联关系通过
        > `JoinConditionIr`(单级) / `RelationIr.conditions`(多级) 解析。

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
    from typing import Dict, List

    from scalim.spec.ir import DerivedFieldIr, FieldIr, JoinConditionIr, RelationIr
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.shared import build_ecommerce_model
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        DerivedFieldIr,
        Dict,
        FieldIr,
        JoinConditionIr,
        List,
        RelationIr,
        build_ecommerce_model,
        build_test_config_small,
        make_chapter_result,
    )


@app.cell
def _(build_ecommerce_model, build_test_config_small):
    # ① 测试配置 + IR 模型构建(复杂复用零件,本场景仅静态诊断,不跑引擎)
    cfg = build_test_config_small()
    model = build_ecommerce_model(cfg)
    print("sources={} fields={}".format(len(model.sources), len(model.fields)))
    return cfg, model


@app.cell(hide_code=True)
def _(mo, model):
    # ② 模型窥视:把复用零件的装配产物直接渲染出来,读者无需跳库
    fields_summary = [
        {"field_id": f.field_id, "name": f.name, "source_id": getattr(f, "source_id", "-"), "kind": type(f).__name__}
        for f in model.fields.values()
    ]
    source_summary = [{"source_id": sid, "preload_forever": src.is_preload_forever()} for sid, src in model.sources.items()]
    mo.vstack(
        [
            mo.md(
                "**模型窥视（读者无需跳库）**:`model.fields` 为 mappingproxy(键=field_id),遍历用 `.values()`;"
                "`DerivedFieldIr` 可能无 `source_id`,用 `getattr` 兜底。"
            ),
            mo.md("**字段结构(`model.fields`)**:"),
            mo.ui.table(fields_summary, selection=None),
            mo.md("**数据源(`model.sources`)**:"),
            mo.ui.table(source_summary, selection=None),
            mo.md("**数据源总数**: {n}".format(n=len(model.sources))),
        ]
    )
    return


@app.cell
def _(DerivedFieldIr, FieldIr, JoinConditionIr, List, RelationIr, model):
    # ③ 静态诊断:按字段类型分类,并解析单级/多级关联表达式
    #    - FieldIr + relation: 关联字段;JoinConditionIr=单级;RelationIr.conditions=多级(可能复合)
    #    - DerivedFieldIr: 派生字段(依赖其它字段计算)
    #    - model.sources 中 is_preload_forever(): 常驻内存缓存的数据源(诊断内存策略)
    relation_fields: list = []
    for field_id, spec in model.fields.items():
        if not isinstance(spec, FieldIr) or not spec.relation:
            continue
        rel = spec.relation
        if isinstance(rel, JoinConditionIr):
            left = "{}.{}".format(rel.left.source.source_id, rel.left.field_name)
            right = "{}.{}".format(rel.right.source.source_id, rel.right.field_name)
            relation_fields.append({"field": field_id, "type": "single", "expr": "{} -> {}".format(left, right)})
        elif isinstance(rel, RelationIr):
            conditions = []
            for cond in rel.conditions:
                left = "{}.{}".format(cond.left.source.source_id, cond.left.field_name)
                right = "{}.{}".format(cond.right.source.source_id, cond.right.field_name)
                conditions.append("{} -> {}".format(left, right))
            relation_fields.append(
                {"field": field_id, "type": "multi" if len(conditions) > 1 else "single", "expr": " AND ".join(conditions)}
            )

    derived_fields = [fid for fid, spec in model.fields.items() if isinstance(spec, DerivedFieldIr)]
    cached_sources = [sid for sid, src in model.sources.items() if src.is_preload_forever()]
    return cached_sources, derived_fields, relation_fields


@app.cell
def _(cached_sources, derived_fields, make_chapter_result, model, relation_fields):
    # ④ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(relation_fields and derived_fields)
    summary = "sources={} fields={} relation_fields={} derived_fields={} cached_sources={}".format(
        len(model.sources), len(model.fields), len(relation_fields), len(derived_fields), len(cached_sources)
    )

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "relation_fields_gt_0": len(relation_fields) > 0,
        "derived_fields_gt_0": len(derived_fields) > 0,
        "sources": len(model.sources),
        "fields": len(model.fields),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "sources": len(model.sources),
            "fields": len(model.fields),
            "relation_fields": relation_fields,
            "derived_fields": derived_fields,
            "cached_sources": cached_sources,
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

    detail_rows = details_to_rows(chapter_result["details"])
    if detail_rows:
        mo.ui.table(detail_rows, selection=None)
    return


def run_chapter():
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
