# Scalim 能力全景图(能力 → 入口 → 实现位置 → 最小推演)

本页的目标是把“框架到底有哪些能力”落到**稳定入口**与**具体实现路径**上。为精简决策服务：你可以据此判断哪些属于 runtime 核心，哪些属于 dev-only 工具/示例。

> 约定：文中的 `IMPL_ROOT` 实际对应 `src/scalim/`。

---

## A. 对外入口(稳定导入路径)

### A1. YAML DSL 一键运行/编译

- 入口：`src/scalim/dsl/by_yaml/__init__.py` 导出的 `run()` / `compile()` / `run_workflow()`
- 实现：`src/scalim/dsl/by_yaml/runtime/entrypoints.py`
- 核心语义：
  - **必须**提供 allowlist：`allowed_modules` 或 `allowed_functions`，否则直接拒绝(安全边界)。
  - `run()` 本质：先 `compile(yaml_path, options)` → 再走执行层统一入口 `src/scalim/execution/run_ir.py::run_ir`。

最小推演(代码形态)：

```python
from scalim.dsl.by_yaml import run
from scalim.sinks.sink_memory import InMemoryRowSink

sink = InMemoryRowSink()
result = run(
    "path/to/report.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    sink=sink,                     # 是否保留内存数据由 sink 决定
    runtime_vars={"order_ids": []}, # $runtime 指令节点用
    parallel_mode="seq",            # 或 "adaptive"
)
print(result.total_rows, result.output_path)
print(sink.rows[:3])
```

对应实现链路：

- allowlist 校验：`src/scalim/dsl/by_yaml/runtime/compiler.py::_ensure_allowlist`
- YAML→`DemandConfig`：`src/scalim/dsl/by_yaml/config_parsing/loader.py::YamlDemandLoader`
- `DemandConfig`→`DemandIr`：`src/scalim/dsl/by_yaml/runtime/conversion.py` + `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- 执行：`src/scalim/execution/run_ir.py::run_ir`

### A2. IR 作为稳定 API(手写需求/二次开发)

- 入口：`src/scalim/spec/ir/__init__.py` (导出 `DemandIr/SourceIr/FieldIr/DerivedFieldIr/...`)
- 典型用途：
  - 不用 YAML，直接手写 `DemandIr`；
  - 或从其它 DSL/配置转换到 IR，再复用 planning/execution。

最小推演：

```python
from scalim.spec.ir import DemandIr, MainSourceIr, SourceIr, SourceRefIr, FieldIr, DerivedFieldIr, KeyIr
from scalim.spec.ir.binding import LoaderIr

def load_orders(): ...
def load_payments(ids): ...

orders = MainSourceIr(source_id="orders", loader=load_orders)
payments = SourceIr(
    source_id="payments",
    key=KeyIr("id"),
    loader_spec=LoaderIr(callable=load_payments),
)

demand = DemandIr.from_irs(
    sources=[payments],
    main_source=orders,
    fields=[
        FieldIr(field_id="order_id", name="订单ID", source=SourceRefIr("orders"), data_key="order_id"),
        # ... 关联字段/派生字段略
        DerivedFieldIr(field_id="total", name="总额", dependencies=("amount",), calculator=lambda amount: sum(amount)),
    ],
)
```

### A3. 规划层(ExecutionPlan)

- 入口：`src/scalim/planning/__init__.py` 导出 `PlanBuilder` / `ExecutionPlan` / operator IR
- 实现：`src/scalim/planning/builder.py`、`src/scalim/planning/plan.py`
- 核心语义：
  - 基于 targets 做依赖闭包与剪枝；
  - 生成 core operators：`load` / `load_ref` / `compute`(写出/释放不属于 planning 产物)。

最小推演：

```python
from scalim.planning import PlanBuilder

plan = PlanBuilder(demand).build(targets=["order_id", "total"])
print(plan.metadata.pruned_fields, plan.metadata.max_depth)
```

### A4. 执行层(统一编排入口 + 引擎)

- DSL-agnostic 统一编排入口：`src/scalim/execution/run_ir.py::run_ir`
  - 请求模型：`ExecutionRequest`
  - 结果模型：`ExecutionResult`
- 引擎：`src/scalim/execution/engine.py::ScalimEngine`
- pipeline：`src/scalim/execution/pipeline/base/pipeline.py::SeqPipeline`
- 批次执行：`src/scalim/execution/executor/batch/executor.py::BatchExecutor`

最小推演(IR 直跑)：

```python
from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryRowSink

plan = PlanBuilder(demand).build()
engine = ScalimEngine(demand=demand, plan=plan, parallel_mode="adaptive", max_workers=0)
sink = InMemoryRowSink()
engine.run(sink=sink)
```

---

## B. YAML DSL 关键能力(按“用户写法”拆分)

### B1. 安全边界：allowlist 引用解析

- 配置面：YAML 中 `loader:` / `call_by:` / `retry.should_retry:` / `normalize.call_by:` 等引用 Python 可调用对象的字段
- 实现：
  - 解析：`src/scalim/dsl/by_yaml/reference_syntax.py`
  - resolver：`src/scalim/dsl/by_yaml/runtime/references.py::SecurePythonReferenceResolver`
  - 编译入口：`src/scalim/dsl/by_yaml/runtime/compiler.py`
- 关键点：
  - 未提供 allowlist 直接拒绝；
  - 相对引用以 `yaml_path` 推导 `base_module_path` 后归一化；
  - 内置危险模块/函数黑名单(例如 `os/subprocess/eval/open/...`)。

### B2. 派生字段 compute：AST 白名单 + 常量 compute

- 配置面：derived field 的 `compute: "sum(amount)"` 等表达式
- 实现：
  - 安全 compute 引擎：`src/scalim/dsl/by_yaml/config_parsing/security.py::SecureComputeEngine`
  - YAML→IR 编译：`src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
  - 执行：`src/scalim/execution/executor/operators/compute/executor.py`
- 关键点：
  - AST 白名单：限制可用节点/运算符/函数调用形式；
  - `is_constant_compute_expression()`：无依赖且无 `Name/Call` 时，可被标记为常量 compute(批次内复用)。

### B3. runtime vars：`$runtime` 指令节点

- 配置面：YAML 中通过 `{$runtime: var_name}` 注入运行期变量
- 入口：`scalim.dsl.by_yaml.run(..., runtime_vars={...})`
- 实现：`src/scalim/dsl/by_yaml/params_template.py` + `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`

### B4. imports / `$import`：配置拆分与合并

- 配置面：YAML 中使用 `imports` / `$import` 引入片段
- 实现：
  - `src/scalim/dsl/by_yaml/config_parsing/imports.py`
  - loader 自动展开：`src/scalim/dsl/by_yaml/config_parsing/loader.py`
  - 校验基于展开后配置：`src/scalim/dsl/by_yaml/config_parsing/validator.py`

### B5. source whole-result normalize：声明式归一化

- 配置面：`sources.<id>.normalize.kind: index_by_key/take_first/project_fields/map_values/...`
- IR：`src/scalim/spec/ir/sources.py::SourceNormalizeIr`(运行时 `apply()`)
- 执行期应用点：
  - preload_forever：`src/scalim/execution/pipeline/base/pipeline.py::_preload_cached_sources`
  - loader 调用后：`src/scalim/execution/executor/operators/load_ref/loader.py`(ref loader) 等

---

## C. 执行与性能能力(按“运行语义”拆分)

### C1. 批处理与 batch_size 语义(含严格类型边界)

- 核心边界：`src/scalim/execution/engine.py::ScalimEngine.__init__`
  - `batch_size=None` 表示 no-chunking(单批处理全部 main rows)
  - `batch_size` 只能是 `None` 或 `int>=1`，拒绝 `0/负数/bool/float/str`

### C2. 并发模式：`seq` vs `adaptive`

- 对外：`parallel_mode="seq"|"adaptive"` (`thread/process` 历史值已移除，会给迁移提示)
- 并发边界：仅限**单批次内**的 `LoadRef(keys)` 扇出/扇入
- 实现：
  - fan-out/fan-in 调度：`src/scalim/execution/adaptive/loadref_scheduler.py`
  - pool/backends：`src/scalim/execution/pipeline/base/_adaptive_pool.py`
  - 执行段切分：`src/scalim/execution/executor/batch/_internal/segments.py`(被 `BatchExecutor` 使用)

### C3. 运行时剪枝/瘦身/释放

- 规划时剪枝(只生成 required 字段)：`src/scalim/planning/builder.py`
- 运行时剪枝(只存 required 字段)：`src/scalim/execution/context.py::BatchContext`
- 释放信号：
  - 列式写入后释放：`src/scalim/execution/pipeline/base/pipeline.py::_write_column_if_target`
  - 行式流式释放：`src/scalim/execution/pipeline/base/_row_emission.py::RowEmissionCoordinator`

### C4. 输出模式：sink 驱动 + tee + NullSink

- 核心：`src/scalim/execution/run_ir.py`
  - 未配置文件输出且未提供 sink：走 `_NullSink`，避免构造返回列表
  - 同时写文件与自定义 sink：尝试 tee(要求两端同为 row sink 或同为 column sink)

### C5. output composition + derived outputs

- 多目标输出：`src/scalim/execution/output_composition.py`
- 派生聚合：`src/scalim/execution/derived_outputs.py`
- 装配入口：`src/scalim/execution/run_ir.py` 的 `ExecutionRequest.output_composition`

---

## D. 可观测性/诊断能力

### D1. 统一分发枢纽：InstrumentationHub

- 事件 want-gate 与懒 payload：`src/scalim/ob/hub.py::InstrumentationHub`
- 事件目录/结构：`src/scalim/events/catalog.py` + `src/scalim/events/events.py`

### D2. 预置 observers

- performance / relation / logs / viz：`src/scalim/ob/presets/`
- YAML 装配：`src/scalim/dsl/by_yaml/runtime/observability.py`(把 YAML observability 配置编译成 observers + spec)

### D3. 可视化回放数据(Scalim Viz artifacts)

- snapshot(依赖图)：`ExecutionPlan.to_viz_graph_snapshot()` → `src/scalim/planning/viz.py`
- 事件流 JSONL：`VizObserver` → `src/scalim/ob/presets/viz.py`
- schedule plan(adaptive 计划视角)：`ExecutionPlan.to_viz_schedule_plan()` → `src/scalim/planning/viz_schedule.py`

---

## E. 运行期防护(guardrails)与重试(loader retry)

### E1. Guardrails

- 策略模型：`src/scalim/execution/guardrails.py`
- 生效点：
  - loader/load_ref 提取与 transform：`src/scalim/execution/executor/operators/_internal/loader_guardrails.py`
  - relation rate guardrail：`src/scalim/execution/executor/runtime/_internal/relation_guardrails.py`
  - compute guardrail：`src/scalim/execution/executor/operators/compute/errors.py`
- YAML 编译：`src/scalim/dsl/by_yaml/runtime/compiler.py::_compile_guardrails_policy`

### E2. Loader retry policy

- 策略与 runner：`src/scalim/execution/loader_retry.py` (`call_with_loader_retry`)
- 调用点(示例)：
  - main source：`src/scalim/execution/pipeline/base/pipeline.py::_load_main_rows`
  - preload_forever：`src/scalim/execution/pipeline/base/pipeline.py::_preload_cached_sources`
  - load_ref：`src/scalim/execution/executor/operators/load_ref/loader.py`(分片调用同样套 retry)
- YAML 编译与 overlay：`src/scalim/dsl/by_yaml/runtime/compiler.py::_compile_loader_retry_policies`

