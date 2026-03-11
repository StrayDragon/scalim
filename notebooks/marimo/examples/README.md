# Scalim 框架示例教程

本目录包含 Scalim 框架的交互式教程和集成测试示例,使用 [marimo](https://marimo.io/) 构建.

## 目录结构

| 目录 | 说明 | 数据源 |
|------|------|--------|
| `demo_big_data_report/` | 大数据场景演示(合成数据) | 内存合成数据 |

## 运行方式

```bash
# 安装 marimo
pip install marimo

# 运行单个示例
marimo run notebooks/marimo/examples/demo_big_data_report/demo_a0_main.py

# 编辑模式(交互式开发)
marimo edit notebooks/marimo/examples/demo_big_data_report/demo_a0_main.py
```

## 文件命名规则

演示文件采用 `demo_{分组字母}{序号}_{功能名}.py` 格式,按功能分组:

| 字母 | 分组 | 说明 |
|------|------|------|
| **a** | 基础入门 | 主入口、执行计划可视化 |
| **b** | Sink 类型 | 各种输出 Sink 演示 |
| **c** | 数据处理 | 外键转换、内存优化等 |
| **d** | Hook/可观测 | Hook 系统、性能监控、可观测性 |
| **e** | 调试工具 | 关联诊断、调试辅助 |

---

# Scalim 框架特性总览

## 维护约定

- 新增示例时优先在已有 demo 或 YAML 配置上扩展;仅当现有结构无法覆盖新场景时再新增文件.
- 变更 `demo_big_data_report/demo_*.py` 文件名或新增/删除示例后,必须同步更新本 README 的功能矩阵与学习路径.

## 核心架构

```
DemandIr (需求定义)
    ↓
PlanBuilder (计划构建)
    ↓
ExecutionPlan (执行计划)
    ↓
ScalimEngine (执行引擎)
    ↓
ISink (输出接口)
```

## 一、数据建模 (IR 层)

### 1.1 数据源定义 (SourceIr)

| 特性 | 说明 | 示例 |
|------|------|------|
| Key (KeyIr) | 单字段/复合 key | `key="order_id"` 或 `key=("region_id", "institution_id")` |
| Key 转换 (lookup_cast) | 类型自动转换 | `key=KeyIr(key="id", cast=int)` |
| 外键声明 (fk_fields) | 声明外键字段集合 | `fk_fields=frozenset({"customer_id", "country_id"})` |
| 缓存模式 | NONE / PRELOAD_FOREVER | `cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER` |
| 加载器绑定 | 参数构建器 | `bindings={"order_id": BindingIr(...)}` |

```python
orders_source = SourceIr(
    source_id="orders",
    key=KeyIr(key="order_id"),
    loader_spec=LoaderIr(
        callable=load_orders,
        bindings={
            "order_id": BindingIr(
                key_field="order_id",
                params_builder=lambda ctx: ((), {"ids": ctx.lookup_keys or set()}),
            )
        },
    ),
    fk_fields=frozenset({"customer_id", "country_id"}),
)
```

### 1.2 字段定义 (FieldIr / DerivedFieldIr)

| 字段类型 | 说明 | 关键属性 |
|----------|------|----------|
| 普通字段 | 直接从数据源读取 | `source`, `data_key` |
| 主键字段 | 标记为主键 | `is_primary=True` |
| 关联字段 | 通过关系关联 | `relation=...` |
| 派生字段 | 计算得出 | `dependencies`, `calculator` |

```python
# 普通字段
name_field = FieldIr(
    field_id="name",
    name="客户姓名",
    source=customers_source,
    data_key="customer_name",
)

# 关联字段
country_name = FieldIr(
    field_id="country_name",
    name="国家名称",
    source=countries_source,
    data_key="name",
    relation=orders_source["country_id"].join(countries_source["country_id"]),
)

# 派生字段
profit = DerivedFieldIr(
    field_id="profit",
    name="利润",
    dependencies=("revenue", "cost"),
    calculator=lambda revenue, cost: revenue - cost,
)
```

### 1.3 关联关系 (RelationIr)

| 关联类型 | 说明 | 语法 |
|----------|------|------|
| 单字段关联 | A.fk → B.key | `source_a["fk"].join(source_b["key"])` |
| 复合键关联 | A.(fk1,fk2) → B.(key1,key2) | `.and_()` 组合多个条件 |
| 多级关联 | A → B → C | 链式 `.and_()` |

```python
# 单字段关联
orders_to_customers = orders["customer_id"].join(customers["customer_id"])

# 复合键关联
orders_to_mapping = (
    orders["region_id"].join(mapping["region_id"])
    .and_(orders["institution_id"].join(mapping["institution_id"]))
)

# 多级关联 (4级链路)
orders_to_dim_d = (
    orders["a_id"].join(dim_a["a_id"])
    .and_(dim_a["b_id"].join(dim_b["b_id"]))
    .and_(dim_b["c_id"].join(dim_c["c_id"]))
    .and_(dim_c["d_id"].join(dim_d["d_id"]))
)
```

### 1.4 外键转换 (FR013)

| 机制 | 作用范围 | 优先级 | 使用场景 |
|------|----------|--------|----------|
| `KeyIr.cast` | 数据源层 | 2 | str→int 类型统一 |
| `LookupStepIr.lookup_cast` | step级别 | 1 (最高) | CSV多值提取 |

```python
# KeyIr.cast: 数据源层
customers_source = SourceIr(
    key=KeyIr(key="customer_id", cast=must_to_int),
    ...
)

# LookupStepIr.lookup_cast: step级别
group_name = FieldIr(
    field_id="group_name",
    source=groups_source,
    lookup_steps=(
        LookupStepIr(
            from_field="group_ids",
            to_source=groups_source,
            lookup_cast=must_get_seps_values_first_int,  # "10,20,30" → 10
        ),
    ),
)
```

---

## 二、执行计划 (Planning)

### 2.1 PlanBuilder

| 功能 | 说明 |
|------|------|
| 依赖分析 | 自动构建字段依赖图 |
| 字段剪枝 (FR021) | 只加载目标字段及其依赖 |
| 拓扑排序 | 确保正确的执行顺序 |
| 循环检测 | 检测并报告循环依赖 |

```python
from scalim.planning import PlanBuilder

builder = PlanBuilder(demand)
plan = builder.build(targets=["order_id", "customer_name", "profit"])

# 查看计划元数据
print(f"总字段: {plan.metadata.total_fields}")
print(f"剪枝字段: {plan.metadata.pruned_fields}")
print(f"最大深度: {plan.metadata.max_depth}")
```

### 2.2 ExecutionPlan 结构

| 组件 | 说明 |
|------|------|
| `operators` | 算子序列 (Load/LoadRef/Compute) |
| `field_order` | 字段执行顺序 |
| `loader_sequence` | 主数据源加载顺序 |
| `ref_loader_sequence` | 关联数据源加载顺序 |
| `preload_sources` | 预加载数据源列表 |
| `stages` | 执行阶段划分 |

---

## 三、执行引擎 (Execution)

### 3.1 ScalimEngine

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `batch_size` | 每批处理的记录数 | 1000 |
| `gc_interval` | GC 触发间隔(批次数) | 10 |
| `parallel_mode` | 执行模式 | "seq" |
| `max_workers` | 并行工作者数量 | 0 (自动) |

```python
from scalim.execution import ScalimEngine

engine = ScalimEngine(
    demand=demand,
    plan=plan,
    hook_manager=hook_manager,
    batch_size=200,
    parallel_mode="seq",  # "seq" | "adaptive"
)

results = engine.run(
    main_rows=demand.main_source.loader(ids=list(range(10000))),
    sink=csv_sink,
)
```

### 3.2 执行模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `seq` | 顺序执行 | 默认,支持所有 Sink |
| `adaptive` | 批次内关联并发(LoadRef keys) | IO 密集型关联,提交点回放 hooks/observers 以保证顺序与线程安全 |

---

## 四、输出 Sink

### 4.1 Sink 类型矩阵

| 类型 | Row Sink | Column Sink | 说明 |
|------|----------|-------------|------|
| CSV | `CSVSink` | `ColumnCSVSink` | 文件输出 |
| Excel | `ExcelSink` | `ColumnExcelSink` | Excel 输出 |
| Pandas | `PandasRowSink` | `PandasColumnSink` | DataFrame 输出 |
| 内存 | `InMemoryRowSink` | `InMemoryColumnSink` | 内存存储 |

### 4.2 选择原则

| 场景 | 推荐 Sink | 原因 |
|------|-----------|------|
| 窄表 (< 50 列) | Row Sink | 行完整性好 |
| 宽表 (50+ 列) | Column Sink | 内存效率高 |
| 测试/调试 | InMemory Sink | 方便检查 |
| 生产输出 | CSV/Excel Sink | 持久化存储 |

```python
# Row Sink 示例
main_rows = demand.main_source.loader()
with CSVSink("output.csv", field_names=targets) as sink:
    engine.run(main_rows=main_rows, sink=sink)

# Column Sink 示例 (宽表推荐)
with ColumnCSVSink("output.csv", field_names=targets) as sink:
    engine.run(main_rows=main_rows, sink=sink)

# Pandas Sink 示例
with PandasColumnSink(field_names=targets) as sink:
    engine.run(main_rows=main_rows, sink=sink)
    df = sink.to_dataframe()
```

---

## 五、Hook 系统 (可观测性)

### 5.1 事件类型

| 事件 | 触发时机 | 用途 |
|------|----------|------|
| `PipelineStartEvent` | Pipeline 开始 | 初始化监控 |
| `PipelineEndEvent` | Pipeline 结束 | 汇总统计 |
| `BatchStartEvent` | 批次开始 | 进度追踪 |
| `BatchEndEvent` | 批次结束 | 批次耗时 |
| `LoaderCallEvent` | Loader 调用 | 数据加载监控 |
| `FieldComputeEvent` | 字段计算 | 计算监控 |
| `FieldSlimEvent` | 字段释放 (FR022) | 内存优化监控 |
| `RowWriteEvent` | 行写入 (FR023) | 流式写入监控 |
| `ColumnWriteEvent` | 列写入 (FR023) | 列式写入监控 |
| `ErrorEvent` | 错误发生 | 错误处理 |

### 5.2 内置 Observer

| Observer | 功能 | 使用场景 |
|------|------|----------|
| `LoggingObserver` | 日志记录 | 调试 |
| `PrettyLoggingObserver` | 美化日志输出 | 交互式运行 |
| `PerformanceObserver` | 统一性能监控 | 生产监控 |
| `MemoryOptimizationObserver` | 内存优化事件 | FR022/FR023 监控 |
| `ExecutionTraceObserver` | 执行追踪 | 详细追踪 |
| `RelationObserver` | 关联可观测性 | 关联诊断 |
| `RowGapObserver` | 行缺口统计 | 数据完整性检查 |
| `VizObserver` | 可视化 JSONL | Scalim Viz 集成 |

### 5.3 自定义 Hook

```python
from scalim.hooks.base import BaseHook, HookManager
from scalim.events.events import BatchEndEvent, LoaderCallEvent

class MyHook(BaseHook):
    def __init__(self):
        self.batch_durations = []
        self.loader_calls = []

    def on_batch_end(self, event: BatchEndEvent) -> None:
        self.batch_durations.append(event.duration)

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        self.loader_calls.append({
            "loader": event.loader_name,
            "duration": event.duration,
            "records": len(event.result),
        })

# 使用 (Hook 用于流程定制)
hook_manager = HookManager()
my_hook = MyHook()
hook_manager.register(my_hook)

engine = ScalimEngine(demand=demand, plan=plan, hook_manager=hook_manager)
```

### 5.4 PerformanceObserver (统一性能监控)

```python
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.performance import PerformanceObserver, PerformanceConfig

config = PerformanceConfig(
    metrics={"duration", "memory", "cpu"},
    sampling_interval=1,
    report_format="console",
    thresholds=PerformanceThresholds(batch_duration_warn=5.0),
)

observer = PerformanceObserver(config=config)
observer_manager = ObserverManager()
observer_manager.register(observer)

# 执行后获取指标
metrics = observer.get_metrics()
print(f"吞吐量: {metrics.throughput:.1f} rows/s")
print(f"峰值内存: {metrics.peak_memory_mb:.1f} MB")
```

### 5.5 RelationObserver (关联可观测性)

```python
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.relations import RelationObserver, RelationConfig

config = RelationConfig(
    enabled=True,
    sampling_rate=0.1,
    log_type_mismatch=True,
    max_samples=100,
)

observer = RelationObserver(config=config)
observer_manager = ObserverManager()
observer_manager.register(observer)

# 执行后获取指标
metrics = observer.get_metrics()
print(f"命中率: {metrics.summary.hit_rate:.2%}")
print(f"类型不匹配: {metrics.summary.type_mismatch_count}")
```

---

## 六、调试工具

### 6.1 RelationDiagnostics

关联关系的调试和诊断工具:

| 方法 | 功能 | 用途 |
|------|------|------|
| `visualize_path()` | 可视化关联路径 | 理解多级关联链路 |
| `check_type_compatibility()` | 检查类型兼容性 | 发现 str/int 类型不匹配 |
| `sample_comparison()` | 样本对比 | 调试关联命中问题 |
| `format_comparison_table()` | 格式化对比表 | 美化输出 |

```python
from scalim.utils.relation_diagnostics import RelationDiagnostics

# 可视化关联路径
relation = orders["customer_id"].join(customers["customer_id"])
print(RelationDiagnostics.visualize_path(relation))

# 检查类型兼容性
warnings = RelationDiagnostics.check_type_compatibility(
    source_a=orders_source,
    source_b=customers_source,
    sample_data_a=orders_data,
    sample_data_b=customers_data,
)

# 样本对比
comparisons = RelationDiagnostics.sample_comparison(
    relation=relation,
    data_a=orders_data,
    data_b=customers_data,
    sample_size=10,
)
print(RelationDiagnostics.format_comparison_table(comparisons))
```

---

## 七、YAML DSL

### 7.1 声明式配置

示例统一维护在 `demo_big_data_report/by_yaml_dsl/`:

- 片段示例: `demo_big_data_report/by_yaml_dsl/skill_snippets.yaml`
- 完整示例: `demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`

独立完整示例(集成验证用): `demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`.

### 7.2 YAML DSL 优势

| 特性 | 说明 |
|------|------|
| 声明式 | 专注于"要什么",而非"怎么做" |
| 可读性 | YAML 格式易于阅读和维护 |
| 模板复用 | YAML Anchor 支持配置复用 |
| 热更新 | 修改 YAML 无需改代码 |
| Schema 验证 | JSON Schema 提供 IDE 支持 |

---

## 八、内存优化 (FR022/FR023)

### 8.1 字段瘦身 (FR022)

- 字段计算完成后,如果不再被其他字段依赖,立即从上下文中删除
- 通过 `FieldSlimEvent` 监控

### 8.2 流式写入 (FR023)

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| 行级流式 | 每行完成后立即写入并释放 | 窄表 |
| 列级流式 | 每列完成后立即写入并释放 | 宽表 (200+ 列) |

```python
# 列级流式写入 (宽表推荐)
with ColumnCSVSink("output.csv", field_names=targets) as sink:
    engine.run(main_rows=main_rows, sink=sink)
    # 每列写入后立即释放内存
```

---

## 九、工具函数

### 9.1 类型转换 (scalim.utils.converters)

| 函数 | 说明 | 异常处理 |
|------|------|----------|
| `to_int` | 转换为 int | 抛异常 |
| `must_to_int` | 转换为 int | 返回 None |
| `to_int_tuple` | 序列转 int 元组 | 抛异常 |
| `must_to_int_tuple` | 序列转 int 元组 | 返回 None |
| `get_seps_values_first_int` | CSV 取首值转 int | 抛异常 |
| `must_get_seps_values_first_int` | CSV 取首值转 int | 返回 None |
| `auto_str_normalize` | 自动字符串规范化 | 返回 None |
| `auto_normalize_key` | 自动关联键规范化 | 返回 None |

---

## 十、功能覆盖矩阵

| FR 编号 | 功能 | 演示文件 |
|---------|------|----------|
| FR002 | 派生字段 | demo_a0_main.py |
| FR003 | 预加载缓存 | demo_a0_main.py |
| FR011 | 多种关联 | demo_c0_transforms_unified.py |
| FR013 | 外键转换 | demo_c0_transforms_unified.py |
| - | 字段转换 | demo_c0_transforms_unified.py |
| FR021 | 字段剪枝 | demo_a1_plan_visualization.py |
| FR022 | 字段瘦身 | demo_c1_memory_optimization.py |
| FR023 | 流式写入 | demo_b0_sinks_unified.py |
| FR031 | Hook 系统 | demo_d0_hooks_unified.py |
| FR032 | 执行计划可视化 | demo_a1_plan_visualization.py |
| - | 性能监控 | demo_d0_hooks_unified.py |
| - | 并行模式对比(`seq`/`adaptive`) | demo_d3_parallel_mode_compare.py |
| - | 关联可观测性 | demo_d1_data_quality_unified.py |
| - | 进程内存监控 | demo_d0_hooks_unified.py |
| - | 行缺口统计 | demo_d1_data_quality_unified.py |
| - | 关联诊断 | demo_e0_relation_diagnostics.py |
| - | YAML DSL | by_yaml_dsl/ |

说明: 一个 unified demo 可能同时覆盖多个能力点,矩阵允许同一文件在多行复用.

---

## 十一、快速开始

### 11.1 最小示例

```python
from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr

# 1. 定义主数据源
def load_orders(ids=None):
    data = [
        {"id": 1, "amount": 100},
        {"id": 2, "amount": 200},
    ]
    if ids is None:
        return data
    return [row for row in data if row["id"] in ids]

main_source = MainSourceIr(
    source_id="orders",
    loader=load_orders,
)

# 2. 定义字段
fields = [
    FieldIr(field_id="id", name="ID", source=main_source, is_primary=True),
    FieldIr(field_id="amount", name="金额", source=main_source),
]

# 3. 构建需求
demand = DemandIr.from_irs(
    sources=[],
    fields=fields,
    main_source=main_source,
)

# 4. 构建计划并执行
plan = PlanBuilder(demand).build(targets=["id", "amount"])
engine = ScalimEngine(demand=demand, plan=plan)
main_rows = main_source.loader(ids=[1, 2])
results = engine.run(main_rows=main_rows)

for row in results:
    print(row)
```

### 11.2 推荐学习路径

1. **入门**: `demo_a0_main.py` - 了解基本流程
2. **计划**: `demo_a1_plan_visualization.py` - 理解执行计划
3. **教程**: `demo_a0_tutor.py` - 贯通 YAML DSL 到执行输出
4. **Sink**: `demo_b0_sinks_unified.py` - 了解输出选项
5. **关联**: `demo_c0_transforms_unified.py` - 掌握关联和类型转换
6. **Hook**: `demo_d0_hooks_unified.py` - 学习可观测性
7. **并发模式**: `demo_d3_parallel_mode_compare.py` - `seq` vs `adaptive` 性能对比 + 三方对拍
8. **可视化**: `demo_d2_visualization.py` - 查看执行过程可视化
9. **DSL**: `by_yaml_dsl/` - 声明式配置
