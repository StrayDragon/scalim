import marimo

__generated_with = "0.19.9"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Scalim 全链路教程: YAML DSL → IR → Plan → Engine → Executor → Sink

    本教程展示 Scalim 框架从配置到输出的完整数据流转过程, 适合 A 组新成员快速理解框架架构.

    ## 架构概览

    ```
    ┌──────────────────────────────────────────────────────────────────────────────┐
    │                              Scalim 数据流转图                               │
    └──────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  YAML DSL   │───▶│     IR      │───▶│    Plan     │───▶│   Engine    │───▶│    Sink     │
    │  (配置层)   │    │  (中间表示)  │    │  (执行计划)  │    │ (执行引擎)   │    │   (输出)    │
    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
         │                   │                   │                   │                   │
         ▼                   ▼                   ▼                   ▼                   ▼
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ • sources   │    │ • SourceIr  │    │ • operators │    │ • Pipeline  │    │ • CSV       │
    │ • fields    │    │ • FieldIr   │    │ • stages    │    │ • Executor  │    │ • Excel     │
    │ • relations │    │ • DemandIr  │    │ • metadata  │    │ • Runtime   │    │ • Memory    │
    │ • output    │    │ • RelationIr│    │ • sequences │    │ • BatchCtx  │    │ • Pandas    │
    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
    ```

    ---
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import sys
    import json
    from pathlib import Path
    from dataclasses import asdict
    from pprint import pformat

    return (Path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 1: YAML DSL - 声明式配置

    YAML DSL 是用户面对的最高层抽象, 声明式地定义数据需求:

    | 配置块 | 说明 | 示例 |
    |--------|------|------|
    | `sources` | 数据源定义 | loader 函数、主键、缓存模式 |
    | `fields` | 字段定义 | 来源、转换、关联 |
    | `relations` | 关联关系 | 单字段/多字段/多级关联 |
    | `output` | 输出配置 | 格式、路径、字段列表 |
    """)
    return


@app.cell
def _(Path):
    _this_dir = Path(__file__).parent
    yaml_path = _this_dir / "by_yaml_dsl" / "ecommerce_report.yaml"

    with open(yaml_path, "r", encoding="utf-8") as f:
        yaml_content = f.read()

    print(f"📄 YAML 配置文件: {yaml_path.name}")
    print(f"📏 文件大小: {len(yaml_content)} 字符")
    return yaml_content, yaml_path


@app.cell
def _(mo, yaml_content):
    mo.md(f"""
    ### 1.1 YAML 配置内容预览

    以下是完整的 YAML DSL 配置 (折叠显示):

    <details>
    <summary>点击展开完整 YAML 配置 ({len(yaml_content)} 字符)</summary>

    ```yaml
    {yaml_content}
    ```
    </details>
    """)
    return


@app.cell
def _(yaml_path):
    # region SCALIM-SKILL:example-full:constraints
    import yaml

    from scalim.dsl.by_yaml.config_parsing.errors import ConfigValidationError
    from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
    from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator

    # 先加载 YAML 内容
    with open(yaml_path, "r", encoding="utf-8") as _f:
        yaml_config = yaml.safe_load(_f)

    # 使用 ConfigValidator 验证配置
    validator = ConfigValidator()
    try:
        validator.validate(yaml_config)
        print("✅ ConfigValidator 验证通过!")
        validation_passed = True
    except ConfigValidationError as e:
        print(f"❌ ConfigValidator 验证失败: {e}")
        for _err in e.errors[:5]:
            print(f"   - {_err}")
        validation_passed = False

    # 然后使用 YamlDemandLoader 加载
    loader = YamlDemandLoader()
    demand_config = loader.load(str(yaml_path))
    # endregion

    print("✅ YAML 解析成功!")
    print(f"   名称: {demand_config.name}")
    print(f"   主数据源: {demand_config.main_source}")
    print(f"   数据源数量: {len(demand_config.sources)}")
    print(f"   字段数量: {len(demand_config.source_fields) + len(demand_config.derived_fields)}")
    print(f"   关联数量: {len(demand_config.relations)}")
    return (demand_config,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 1.2 DemandConfig 结构

    `DemandConfig` 是 YAML 解析后的配置对象, 包含所有用户定义的信息:
    """)
    return


@app.cell
def _(demand_config, mo):
    _config_summary = []

    _config_summary.append("**Sources (数据源)**:")
    for _source_id, _source_cfg in list(demand_config.sources.items())[:3]:
        _key_str = _source_cfg.key if isinstance(_source_cfg.key, str) else str(_source_cfg.key)
        _config_summary.append(f"  - `{_source_id}`: key={_key_str}, cache={_source_cfg.cache_mode or 'none'}")
    if len(demand_config.sources) > 3:
        _config_summary.append(f"  - ... 共 {len(demand_config.sources)} 个数据源")

    _config_summary.append("\n**Source Fields (来源字段)**:")
    for _field_id, _field_cfg in list(demand_config.source_fields.items())[:5]:
        _relation_str = f", relation={_field_cfg.relation}" if _field_cfg.relation else ""
        _field_name = _field_cfg.field or _field_id
        _config_summary.append(f"  - `{_field_id}`: source={_field_cfg.source}, field={_field_name}{_relation_str}")
    if len(demand_config.source_fields) > 5:
        _config_summary.append(f"  - ... 共 {len(demand_config.source_fields)} 个来源字段")

    _config_summary.append("\n**Derived Fields (派生字段)**:")
    for _field_id, _derived_cfg in demand_config.derived_fields.items():
        _config_summary.append(f"  - `{_field_id}`: depends_on={_derived_cfg.depends_on}")

    _config_summary.append("\n**Relations (关联关系)**:")
    for _rel_id, _rel_cfg in demand_config.relations.items():
        _config_summary.append(f"  - `{_rel_id}`: steps={len(_rel_cfg.steps)}")

    mo.md("\n".join(_config_summary))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 2: IR (Intermediate Representation) - 中间表示

    IR 是框架内部使用的类型安全的数据结构, 将 YAML 配置转换为可执行的对象图:

    | IR 类型 | 说明 | 关键属性 |
    |---------|------|----------|
    | `SourceIr` | 数据源 | key, loader_spec, cache_mode |
    | `FieldIr` | 字段 | source, relation/lookup_steps, transform |
    | `DerivedFieldIr` | 派生字段 | dependencies, calculator |
    | `RelationIr` | 关联关系 | conditions (JoinConditionIr[]) |
    | `DemandIr` | 顶层需求 | sources, fields, main_source |
    """)
    return


@app.cell
def _(demand_config):
    from scalim.dsl.by_yaml.runtime.conversion import ConfigToIRConverter
    from scalim.dsl.by_yaml.runtime.references import PythonReferenceResolver

    allowed_modules = frozenset(["notebooks.marimo.examples.demo_big_data_report._loaders"])
    resolver = PythonReferenceResolver(allowed_modules=allowed_modules)
    converter = ConfigToIRConverter(resolver=resolver)

    demand_ir = converter.convert(demand_config)

    print("✅ IR 转换成功!")
    print(f"   需求名: {demand_ir.name}")
    print(f"   数据源数量: {len(demand_ir.sources)}")
    print(f"   字段数量: {len(demand_ir.fields)}")
    print(f"   主数据源: {demand_ir.main_source.source_id}")
    print(f"   批大小提示: {demand_ir.batch_size_hint}")
    return (demand_ir,)


@app.cell
def _(demand_config, demand_ir):
    from scalim.spec.ir import FieldIr as _FieldIr

    _relation = demand_config.relations.get("orders_to_categories")
    assert _relation is not None
    assert _relation.steps[1].from_ == "products.product_category_id"

    _field_spec = demand_ir.fields.get("category_name")
    assert isinstance(_field_spec, _FieldIr)
    assert _field_spec.lookup_steps is not None
    assert _field_spec.lookup_steps[-1].from_field == "category_id"

    print("✅ 关联步骤支持使用 `field_id`: `products.product_category_id` → `data_key` `category_id`")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2.1 SourceIr 详解

    `SourceIr` 封装了数据源的完整信息:
    """)
    return


@app.cell
def _(demand_ir, mo):
    _source_details = []

    for _source_id, _source_ir in list(demand_ir.sources.items())[:4]:
        _key_key = _source_ir.key.key
        _key_str = _key_key if isinstance(_key_key, str) else str(_key_key)
        _cache_str = "PRELOAD_FOREVER" if _source_ir.is_preload_forever() else "NONE"
        _loader_name = getattr(_source_ir.loader_spec.callable, "__name__", str(_source_ir.loader_spec.callable))

        _bindings_info = []
        for _bind_key, _binding in _source_ir.loader_spec.bindings.items():
            _bind_key_str = _bind_key if isinstance(_bind_key, str) else str(_bind_key)
            _bindings_info.append(f"`{_bind_key_str}`")

        _source_details.append(f"""
    #### `{_source_id}`
    - **Key**: `{_key_str}`
    - **Cache Mode**: `{_cache_str}`
    - **Loader**: `{_loader_name}`
    - **Bindings**: {", ".join(_bindings_info) if _bindings_info else "None"}
    """)

    mo.md("".join(_source_details))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2.2 FieldIr 详解

    `FieldIr` 和 `DerivedFieldIr` 定义了字段的来源和计算逻辑:
    """)
    return


@app.cell
def _(demand_ir, mo):
    from scalim.spec.ir import DerivedFieldIr, FieldIr

    _field_table = [{"field_id": "字段ID", "类型": "类型", "来源": "来源", "关联": "关联", "依赖": "依赖"}]

    for _field_id, _field_spec in list(demand_ir.fields.items())[:10]:
        if isinstance(_field_spec, FieldIr):
            _rel_str = "有" if (_field_spec.relation or _field_spec.lookup_steps) else "-"
            _field_table.append(
                {
                    "field_id": _field_id,
                    "类型": "FieldIr",
                    "来源": _field_spec.source.source_id,
                    "关联": _rel_str,
                    "依赖": "-",
                }
            )
        elif isinstance(_field_spec, DerivedFieldIr):
            _field_table.append(
                {
                    "field_id": _field_id,
                    "类型": "DerivedFieldIr",
                    "来源": "-",
                    "关联": "-",
                    "依赖": ", ".join(_field_spec.dependencies[:3]) + ("..." if len(_field_spec.dependencies) > 3 else ""),
                }
            )

    mo.ui.table(_field_table[1:], selection=None)
    return (FieldIr,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 2.3 RelationIr 详解

    `RelationIr` 和 `JoinConditionIr` 表达表间关联:
    """)
    return


@app.cell
def _(FieldIr, demand_ir, mo):
    _relation_examples = []

    for _field_id, _field_spec in demand_ir.fields.items():
        if isinstance(_field_spec, FieldIr):
            if _field_spec.relation:
                from scalim.spec.ir import JoinConditionIr, RelationIr

                _rel = _field_spec.relation
                if isinstance(_rel, JoinConditionIr):
                    _left = f"{_rel.left.source.source_id}.{_rel.left.field_name}"
                    _right = f"{_rel.right.source.source_id}.{_rel.right.field_name}"
                    _relation_examples.append(f"- **{_field_id}** (JoinCondition): `{_left}` → `{_right}`")
                elif isinstance(_rel, RelationIr):
                    _conditions = []
                    for _cond in _rel.conditions:
                        _left = f"{_cond.left.source.source_id}.{_cond.left.field_name}"
                        _right = f"{_cond.right.source.source_id}.{_cond.right.field_name}"
                        _conditions.append(f"`{_left}` → `{_right}`")
                    _relation_examples.append(f"- **{_field_id}** (RelationIr): {' AND '.join(_conditions)}")
            elif _field_spec.lookup_steps:
                _steps = []
                for _step in _field_spec.lookup_steps:
                    if isinstance(_step.from_field, (list, tuple)):
                        _from_fields = ", ".join(_step.from_field)
                    else:
                        _from_fields = _step.from_field
                    _to_fields = ", ".join(_step.get_to_fields_or_source_key())
                    _steps.append(f"`{_from_fields}` → `{_step.to_source.source_id}.{_to_fields}`")
                _relation_examples.append(f"- **{_field_id}** (LookupSteps): {' → '.join(_steps)}")

            if len(_relation_examples) >= 5:
                break

    mo.md("**字段关联示例**:\n\n" + "\n".join(_relation_examples))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 3: Plan - 执行计划

    `ExecutionPlan` 是物理执行计划, 包含完整的算子序列:

    | 组件 | 说明 |
    |------|------|
    | `operators` | 算子序列 (按执行顺序) |
    | `stages` | 执行阶段 (可并行的字段分组) |
    | `loader_sequence` | 主数据加载顺序 |
    | `ref_loader_sequence` | 关联数据加载顺序 |
    | `metadata` | 计划元数据 |
    """)
    return


@app.cell
def _(demand_config, demand_ir):
    from scalim.planning import PlanBuilder

    target_fields = demand_config.output.fields if demand_config.output else None

    plan_builder = PlanBuilder(demand_ir)
    execution_plan = plan_builder.build(targets=target_fields)

    print("✅ 执行计划构建成功!")
    print(f"   目标字段数: {len(target_fields) if target_fields else len(demand_ir.fields)}")
    print(f"   算子数量: {len(execution_plan.operators)}")
    print(f"   执行阶段数: {len(execution_plan.stages)}")
    print(f"   字段执行顺序: {len(execution_plan.field_order)} 个字段")
    return (execution_plan,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3.1 PlanMetadata - 计划元数据
    """)
    return


@app.cell
def _(execution_plan, mo):
    meta = execution_plan.metadata

    mo.md(f"""
    | 指标 | 值 |
    |------|-----|
    | 总字段数 | {meta.total_fields} |
    | 使用数据源数 | {meta.total_sources} |
    | Loader 调用数 | {meta.total_loaders} |
    | 剪枝字段数 | {meta.pruned_fields} |
    | 最大依赖深度 | {meta.max_depth} |
    | 有派生字段 | {"✅" if meta.has_derived_fields else "❌"} |
    | 有关联字段 | {"✅" if meta.has_ref_fields else "❌"} |
    | 预加载数据源 | {", ".join(meta.cached_sources) if meta.cached_sources else "None"} |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3.2 Operators - 算子序列

    算子是执行的基本单元, 按顺序执行:
    """)
    return


@app.cell
def _(execution_plan, mo):
    from scalim.planning import (
        LoadOperatorIr,
        LoadRefOperatorIr,
        ComputeOperatorIr,
    )

    _operator_table = []

    for _op in execution_plan.operators:
        if isinstance(_op, LoadOperatorIr):
            _fields_str = ", ".join(_op.field_keys[:3])
            if len(_op.field_keys) > 3:
                _fields_str += f"... (+{len(_op.field_keys) - 3})"
            _operator_table.append(
                {
                    "算子ID": _op.operator_id,
                    "类型": "Load",
                    "数据源": _op.source.source_id,
                    "字段/详情": _fields_str,
                }
            )
        elif isinstance(_op, LoadRefOperatorIr):
            _operator_table.append(
                {
                    "算子ID": _op.operator_id,
                    "类型": "LoadRef",
                    "数据源": _op.source.source_id,
                    "字段/详情": _op.field_key,
                }
            )
        elif isinstance(_op, ComputeOperatorIr):
            _deps_str = ", ".join(_op.input_fields[:3])
            if len(_op.input_fields) > 3:
                _deps_str += "..."
            _operator_table.append(
                {
                    "算子ID": _op.operator_id,
                    "类型": "Compute",
                    "数据源": "-",
                    "字段/详情": f"{_op.field_spec.field_id} = f({_deps_str})",
                }
            )

    mo.ui.table(_operator_table, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3.3 Stages - 执行阶段

    Stage 将可并行执行的字段分组:
    """)
    return


@app.cell
def _(execution_plan, mo):
    _stage_info = []
    for _stage in execution_plan.stages:
        _fields_preview = ", ".join(_stage.field_keys[:5])
        if len(_stage.field_keys) > 5:
            _fields_preview += f"... (+{len(_stage.field_keys) - 5})"
        _stage_info.append(
            {
                "阶段": _stage.stage_id,
                "层级": _stage.level,
                "字段数": len(_stage.field_keys),
                "字段预览": _fields_preview,
            }
        )

    mo.ui.table(_stage_info, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 3.4 Loader Sequence - 加载顺序
    """)
    return


@app.cell
def _(execution_plan, mo):
    _loader_info = []

    _loader_info.append("**主数据加载 (loader_sequence)**:")
    for _source, _fields in execution_plan.loader_sequence:
        _fields_str = ", ".join(_fields[:5])
        if len(_fields) > 5:
            _fields_str += f"... (+{len(_fields) - 5})"
        _loader_info.append(f"  - `{_source.source_id}`: {_fields_str}")

    _loader_info.append("\n**关联数据加载 (ref_loader_sequence)**:")
    for _source, _ref_fields in execution_plan.ref_loader_sequence:
        _field_names = [f[0] for f in _ref_fields]
        _fields_str = ", ".join(_field_names[:3])
        if len(_field_names) > 3:
            _fields_str += f"... (+{len(_field_names) - 3})"
        _loader_info.append(f"  - `{_source.source_id}`: {_fields_str}")

    mo.md("\n".join(_loader_info))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 4: Engine - 执行引擎

    `ScalimEngine` 是计算引擎, 驱动 Pipeline → Executor → Sink 的执行流程:

	    ```
	    Engine
	      │
	      ├── Pipeline (流水线)
	      │     └── SeqPipeline
	      │           ├── parallel_mode="seq"      (纯串行)
	      │           └── parallel_mode="adaptive" (批次内 LoadRef 自动 fan-out/fan-in)
	      │
	      ├── Executor (执行器)
	      │     ├── BatchExecutor (批次执行器)
	      │     │     ├── LoadOperatorExecutor
      │     │     ├── LoadRefOperatorExecutor
      │     │     └── ComputeOperatorExecutor
      │     │
      │     └── ExecutionRuntime (运行时)
      │           ├── preloaded_cache
      │           ├── hook_manager
      │           └── field_specs
      │
      └── BatchContext (批次上下文)
            └── field_values: Dict[field_key, Dict[batch_row_nth, value]]
    ```
    """)
    return


@app.cell
def _(demand_ir, execution_plan):
    from scalim.execution import ScalimEngine
    from scalim.hooks.base import HookManager

    hook_manager = HookManager()

    engine = ScalimEngine(
        demand=demand_ir,
        plan=execution_plan,
        hook_manager=hook_manager,
        batch_size=100,
        gc_interval=10,
        parallel_mode="seq",
    )

    print("✅ 执行引擎初始化成功!")
    print(f"   批大小: {engine.batch_size}")
    print(f"   GC 间隔: {engine.gc_interval}")
    print(f"   流水线类型: {type(engine._pipeline).__name__}")
    return (engine,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 4.1 ExecutionRuntime - 执行运行时

    `ExecutionRuntime` 维护执行期间的共享状态:
    """)
    return


@app.cell
def _(engine, mo):
    _runtime = engine._pipeline.runtime

    _runtime_info = f"""
    | 属性 | 值 |
    |------|-----|
    | 预加载缓存 | {len(_runtime.preloaded_cache)} 个数据源 |
    | 字段规格数 | {len(_runtime.field_specs)} |
    | 关键字段 | {len(_runtime.key_fields)} |
    | 目标字段 | {len(_runtime.target_fields)} |
    | 主键字段 | `{_runtime.primary_field}` |
    """

    mo.md(_runtime_info)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 4.2 BatchExecutor - 批次执行器

    `BatchExecutor` 执行单个批次的所有算子:
    """)
    return


@app.cell
def _(engine, mo):
    _executor = engine._pipeline.executor

    _executor_info = f"""
    **BatchExecutor 算子执行器注册表**:

    | 算子类型 | 执行器 |
    |----------|--------|
    | `load` | `{type(_executor._executors.get("load")).__name__}` |
    | `load_ref` | `{type(_executor._executors.get("load_ref")).__name__}` |
    | `compute` | `{type(_executor._executors.get("compute")).__name__}` |
    | `write_column` | `{type(_executor._executors.get("write_column")).__name__}` |
    | `write_row` | `{type(_executor._executors.get("write_row")).__name__}` |
    | `release` | `{type(_executor._executors.get("release")).__name__}` |
    """

    mo.md(_executor_info)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 5: Sink - 输出

    Sink 是框架的输出接口, 支持多种输出格式:

    | Sink 类型 | 接口 | 说明 |
    |-----------|------|------|
    | `InMemoryListSink` | IRowSink | 内存存储, 用于测试 |
    | `CSVSink` | IRowSink | 行式 CSV 输出 |
    | `ColumnCSVSink` | IColumnSink | 列式 CSV 输出 |
    | `ExcelSink` | IRowSink | 行式 Excel 输出 |
    | `ColumnExcelSink` | IColumnSink | 列式 Excel 输出 |
    | `PandasSink` | ISink | Pandas DataFrame 输出 |
    """)
    return


@app.cell
def _():
    from scalim.sinks.sink_memory import InMemoryListSink

    memory_sink = InMemoryListSink()

    print("✅ InMemoryListSink 创建成功!")
    print(f"   类型: {type(memory_sink).__name__}")
    print(f"   接口: IRowSink (行式写入)")
    return (memory_sink,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 6: 执行并查看结果

    现在执行完整的 Pipeline, 将结果写入 Sink:
    """)
    return


@app.cell
def _():
    primary_keys = list(range(1, 21))
    print(f"📥 样本主键: {len(primary_keys)} 条")
    print(f"   范围: {primary_keys[0]} ~ {primary_keys[-1]}")
    return (primary_keys,)


@app.cell
def _(engine, memory_sink, primary_keys):
    import time as _time

    _start_time = _time.time()
    main_rows = engine.demand.main_source.loader(ids=primary_keys) if engine.demand.main_source else []
    _results = engine.run(main_rows=main_rows, sink=memory_sink)
    _duration = _time.time() - _start_time

    output_data = memory_sink.get_data()

    print(f"✅ 执行完成!")
    print(f"   总行数: {len(output_data)}")
    print(f"   执行耗时: {_duration:.3f}s")
    if _duration > 0:
        print(f"   吞吐量: {len(output_data) / _duration:.0f} 行/秒")
    return (output_data,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6.1 输出数据预览
    """)
    return


@app.cell
def _(mo, output_data):
    mo.ui.table(output_data[:20], selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6.2 数据统计
    """)
    return


@app.cell
def _(mo, output_data):
    if output_data:
        _first_row = output_data[0]
        _field_count = len(_first_row)
        _non_null_counts = {k: sum(1 for row in output_data if row.get(k) is not None) for k in _first_row.keys()}

        _stats_table = []
        for _field_key, _count in list(_non_null_counts.items())[:10]:
            _sample_value = output_data[0].get(_field_key)
            _sample_str = str(_sample_value)[:30] + "..." if len(str(_sample_value)) > 30 else str(_sample_value)
            _stats_table.append(
                {
                    "字段": _field_key,
                    "非空数": _count,
                    "非空率": f"{_count / len(output_data) * 100:.1f}%",
                    "示例值": _sample_str,
                }
            )

        mo.ui.table(_stats_table, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 6.3 对拍验证

    使用对照组验证 Scalim 输出正确性:
    """)
    return


@app.cell
def _(Path, output_data):
    import sys as _sys

    _this_dir = Path(__file__).parent
    if str(_this_dir) not in _sys.path:
        _sys.path.insert(0, str(_this_dir))

    from _verification import verify_scalim_output, get_relation_check_results

    _output_data = []
    for _row in output_data:
        _patched = dict(_row)
        if "region_name" not in _patched and "region_name_value" in _patched:
            _patched["region_name"] = _patched.get("region_name_value")
        _output_data.append(_patched)

    verification = verify_scalim_output(_output_data)
    verification.raise_if_failed()
    print(verification)
    return get_relation_check_results, verification


@app.cell
def _(get_relation_check_results, mo, verification):
    checks = get_relation_check_results(verification)
    mo.ui.table(checks, selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## Step 7: 便捷函数 - run()

    `run()` 提供一站式执行能力,并通过显式参数表达输出策略:

    | 用法 | 说明 |
    |------|------|
    | `run()` | 完整执行,返回 `RunResult` |
    | `run(..., overrides=RunOverrides(output=OutputOverrides(path=...)))` | 覆盖 YAML 的输出路径并输出到文件(具体格式由 YAML `output.format` 或 overrides 决定) |
    | `run(..., sink=InMemoryRowSink())` | 将结果写入内存 sink,运行后通过 sink 获取数据 |

    **安全特性**: 需要配置 allowlist 来限制可调用的模块/函数
    """)
    return


@app.cell
def _(Path, yaml_path):
    # region SCALIM-SKILL:example-full:run-yaml
    from scalim.dsl.by_yaml import run
    from scalim.sinks.sink_memory import InMemoryRowSink

    # 注意: `run()` 需要 `allowlist` 配置
    # 这里我们使用当前目录的 _loaders 模块
    _this_dir = Path(__file__).parent
    _loaders_module = "notebooks.marimo.examples.demo_big_data_report._loaders"

    try:
        sink = InMemoryRowSink()
        result = run(
            str(yaml_path),
            allowed_modules=frozenset([_loaders_module]),
            sink=sink,
        )
        print("✅ `run()` 执行成功!")
        print(f"   总行数: {result.total_rows}")
        print(f"   耗时: {result.duration:.3f}s")
        print(f"   输出路径: {result.output_path or '(内存)'}")
    except Exception as e:
        print(f"⚠️ `run()` 执行失败: {e}")
        print("   (YAML 配置可能引用了未授权的模块)")
        result = None
    # endregion
    return (result,)


@app.cell
def _(result):
    rows = None
    if result is not None and result.sink is not None and hasattr(result.sink, "get_data"):
        rows = result.sink.get_data()

    if not rows:
        print("⚠️ 输出行对拍校验跳过(`run()` 未产出内存数据)")
        mismatch = None
    else:
        match_fields = ["rows_name_match", "rows_level_match"]
        mismatch = 0
        for row in rows:
            for field in match_fields:
                if field not in row or not row.get(field):
                    mismatch += 1
                    break

        if mismatch:
            print(f"❌ 输出行对拍失败: {mismatch} 行不一致")
        else:
            print("✅ 输出行对拍通过: 所有行一致")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ---
    ## 总结

    ### 数据流转回顾

    ```
    YAML DSL ──────────────────────────────────────────────────────────────▶ Sink Output
         │                                                                        ▲
         │ YamlDemandLoader                                                       │
         ▼                                                                        │
    DemandConfig ──▶ ConfigToIRConverter ──▶ DemandIr ──▶ PlanBuilder ──▶ ExecutionPlan
                                                │                              │
                                                │                              │
                                                ▼                              ▼
                                           ScalimEngine ◀─────────────────────┘
                                                │
                                                ├── Pipeline.run()
                                                │     │
                                                │     ├── preload_sources()
                                                │     │
                                                │     └── for batch in batches:
                                                │           BatchExecutor.execute_batch()
                                                │             │
                                                │             ├── LoadOperatorExecutor
                                                │             ├── LoadRefOperatorExecutor
                                                │             └── ComputeOperatorExecutor
                                                │
                                                └── Sink.write_batch() / write_row()
    ```

    ### 关键模块职责

    | 模块 | 职责 | 输入 | 输出 |
    |------|------|------|------|
    | `scalim.dsl.by_yaml` | YAML 解析与转换 | YAML 文件 | DemandConfig |
    | `scalim.dsl.by_yaml.runtime` | 便捷执行函数 | YAML 文件 | RunResult |
    | `scalim.spec.ir` | IR 类型定义 | - | SourceIr, FieldIr, DemandIr |
    | `scalim.planning` | 执行计划构建 | DemandIr | ExecutionPlan |
    | `scalim.execution` | 计划执行 | ExecutionPlan | 数据行 |
    | `scalim.sinks` | 输出适配 | 数据行 | CSV/Excel/Memory |
    | `scalim.ob` | 可观测性 | 事件 | 日志/指标 |

    ### 扩展点

    1. **自定义 Loader**: 实现新的数据源加载函数
    2. **自定义 Sink**: 实现 `ISink` / `IRowSink` / `IColumnSink` 接口
    3. **自定义 Hook**: 实现 `BaseHook` 接口进行流程定制
    4. **自定义 Observer**: 实现 `Observer.on_event` 进行事件监听
    5. **自定义 Transform**: 字段值转换函数
    """)
    return


if __name__ == "__main__":
    app.run()
