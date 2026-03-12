import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 关联诊断演示

    展示如何诊断和调试关联问题:

    | 诊断类型 | 说明 |
    |----------|------|
    | 关联配置检查 | 检查关联定义是否正确 |
    | 数据匹配检查 | 检查外键是否能匹配到目标数据 |
    | 空值分析 | 分析关联失败的原因 |

    **特点**: 不执行 Scalim,仅分析模型配置
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

    from _loaders import ECommerceConfig, set_config
    from _shared import TARGET_FIELDS_FULL, build_ecommerce_model

    return (
        ECommerceConfig,
        TARGET_FIELDS_FULL,
        build_ecommerce_model,
        set_config,
    )


@app.cell
def _(ECommerceConfig, build_ecommerce_model, mo, set_config):
    cfg = ECommerceConfig(order_count=100)
    set_config(cfg)
    model = build_ecommerce_model()

    mo.hstack(
        [
            mo.stat(value=f"{len(model.sources)}", label="数据源数", bordered=True),
            mo.stat(value=f"{len(model.fields)}", label="字段数", bordered=True),
        ],
        justify="start",
        gap=1,
    )
    return cfg, model


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 数据源分析
    """)
    return


@app.cell
def _(mo, model):
    source_info = []
    for source_id, source in model.sources.items():
        key_str = source.key.key if isinstance(source.key.key, str) else str(source.key.key)
        cache = "PRELOAD" if source.is_preload_forever() else "NONE"
        source_info.append({"数据源": source_id, "Key": key_str, "缓存模式": cache})

    mo.ui.table(source_info)
    return (source_info,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 关联关系分析
    """)
    return


@app.cell
def _(model):
    from scalim.spec.ir import FieldIr, JoinConditionIr, RelationIr

    relation_info = []

    for _field_id, _fspec in model.fields.items():
        if isinstance(_fspec, FieldIr) and _fspec.relation:
            _rel = _fspec.relation
            if isinstance(_rel, JoinConditionIr):
                _left = f"{_rel.left.source.source_id}.{_rel.left.field_name}"
                _right = f"{_rel.right.source.source_id}.{_rel.right.field_name}"
                relation_info.append({"字段": _field_id, "类型": "单级", "关联": f"{_left} → {_right}"})
            elif isinstance(_rel, RelationIr):
                _conditions = []
                for _cond in _rel.conditions:
                    _left = f"{_cond.left.source.source_id}.{_cond.left.field_name}"
                    _right = f"{_cond.right.source.source_id}.{_cond.right.field_name}"
                    _conditions.append(f"{_left} → {_right}")
                _rel_type = "多级" if len(_conditions) > 1 else "单级"
                relation_info.append({"字段": _field_id, "类型": _rel_type, "关联": " AND ".join(_conditions)})

    print(f"共 {len(relation_info)} 个关联字段")
    return FieldIr, JoinConditionIr, RelationIr, relation_info


@app.cell
def _(mo, relation_info):
    mo.ui.table(relation_info[:15])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 关联类型统计
    """)
    return


@app.cell
def _(relation_info):
    type_stats = {}
    for r in relation_info:
        t = r["类型"]
        type_stats[t] = type_stats.get(t, 0) + 1

    print("关联类型统计:")
    for t, count in type_stats.items():
        print(f"  {t}: {count}")
    return (type_stats,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 派生字段分析
    """)
    return


@app.cell
def _(model):
    from scalim.spec.ir import DerivedFieldIr

    derived_info = []

    for _fid, _fs in model.fields.items():
        if isinstance(_fs, DerivedFieldIr):
            _deps = ", ".join(_fs.dependencies)
            derived_info.append({"字段": _fid, "依赖": _deps})

    print(f"共 {len(derived_info)} 个派生字段")
    for _d in derived_info:
        print(f"  {_d['字段']}: 依赖 ({_d['依赖']})")
    return DerivedFieldIr, derived_info


@app.cell(hide_code=True)
def _(mo):
    mo.callout(
        mo.md(r"""
        ## 诊断完成

        本演示仅分析模型配置,不执行实际数据处理.
        要验证实际数据处理结果,请运行其他 demo.
        """),
        kind="info",
    )
    return


if __name__ == "__main__":
    app.run()
