# 核心链路真值推演：YAML/Python → IR → Plan → Execution → 输出

本页用“可执行的事实链路”把 Scalim 的运行时行为钉死，避免只看文档/只看 spec 造成误判。重点放在**优先级**、**默认行为**、**安全边界**与**你删目录时会不会影响 runtime**。

---

## 0) 总览：一键 `run(yaml_path=...)` 实际做了什么

入口：`src/scalim/dsl/by_yaml/runtime/entrypoints.py::run`

1. 构造 `RunOptions`(allowed_modules/sink/overrides/parallel_mode/runtime_vars...)
2. `compile(yaml_path, options)`：
   - allowlist 校验(必需)
   - `YamlDemandLoader.load()` 加载 YAML，包含 imports 展开
   - `SecurePythonReferenceResolver` 解析所有“引用到 Python 可调用对象”的字段
   - `ConfigToIRConverter.convert()` 生成 `DemandIr`
   - `build_request(...)` 生成 execution 侧 `ExecutionRequest`(DSL-agnostic)
3. execution 统一编排入口 `src/scalim/execution/run_ir.py::run_ir(demand_ir, request)`：
   - `PlanBuilder(demand_ir).build(targets=...)` 构建 `ExecutionPlan`
   - 装配 observers/hooks/viz observer
   - 装配 sink(文件 sink / NullSink / tee / output_composition router)
   - 创建 `ScalimEngine` → `engine.run(...)`
   - best-effort close sink + close observers
   - 返回 `ExecutionResult`(DSL-agnostic)，YAML wrapper 再包装成 `RunResult`

> 结论：`frontend/` 与 `notebooks/` 不在这条 runtime 主链路中；它们影响的是工具/回归/文档，而非核心执行行为。

---

## 1) YAML 读取 + 校验：你以为的“schema 校验”与实际语义校验

### 1.1 imports 展开发生在什么时候

- imports 展开：`src/scalim/dsl/by_yaml/config_parsing/imports.py`
- 触发点：`src/scalim/dsl/by_yaml/config_parsing/loader.py::YamlDemandLoader`
- 结论：validator 面对的是“展开后的最终配置”。

### 1.2 CLI `schema validate` vs `validate`

- CLI 入口：`src/scalim/cli/yaml_dsl.py`
  - `scalim-cli yaml-dsl schema validate`：用 JSON schema 做结构校验(依赖 `jsonschema` 可选依赖)
  - `scalim-cli yaml-dsl validate`：走内部 `ConfigValidator` 做语义校验 + unknown fields 检查 + 定位信息

> 如果你删了 `frontend/scalim-yaml-dsl-editor/`，不会影响这部分能力；只影响“写 YAML 时的 IDE/网页体验”。

---

## 2) 安全边界：为什么 `run()` 强制 require allowlist

关键位置：`src/scalim/dsl/by_yaml/runtime/compiler.py::_ensure_allowlist`

你必须提供：

- `allowed_modules=frozenset([...])`，或
- `allowed_functions=frozenset([...])`

原因：YAML 中的 `loader` / `call_by` / `normalize.call_by` / `retry.should_retry` 等字段会触发 Python 引用解析与导入，allowlist 是“配置输入不可信”时的安全边界。

引用解析实现：`src/scalim/dsl/by_yaml/runtime/references.py::SecurePythonReferenceResolver`

关键事实：

- 支持 dotted 与 class-style 引用；
- 支持相对模块引用(`.` 开头)，但要求 `base_module_path` 能从 `yaml_path + sys.path` 推导；
- 拒绝危险模块/危险函数(黑名单)；
- 允许列表可使用 `*` 通配符，但会打 warning(用于可信环境，不建议生产)。

---

## 3) YAML → IR：哪些东西会“变成不可变 IR”

IR 入口：`src/scalim/spec/ir/__init__.py`

### 3.1 field extract 的“规范化段”(typed segments)

- IR 存储：
  - `FieldIr.extract_expr`：诊断友好的表达文本
  - `FieldIr.extract_segments`：typed segments(`str|int`)，用于运行时 `extract_field_segments`
- 编译：
  - `src/scalim/dsl/by_yaml/config_parsing/field_extract.py`
  - `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
- 执行读取：
  - `src/scalim/execution/executor/helpers/field_access.py::extract_field_segments`

这意味着：即便你删掉 notebooks/examples，只要 tests 覆盖了 `extract_segments` 的编译与读取行为，runtime 仍可稳定。

### 3.2 derived compute 的两个形态：`compute` vs `call_by`

- `compute`：字符串表达式，走 SecureComputeEngine(AST 白名单)
  - `src/scalim/dsl/by_yaml/config_parsing/security.py`
- `call_by`：安全引用 + 受控 `$ctx` 访问规则(另一路解析器)
  - 解析/约束在 `src/scalim/dsl/by_yaml/reference_syntax.py` 与 runtime conversion 中体现

### 3.3 runtime vars 与 params template

- `$runtime` 指令节点在编译期被解析成 template IR；
- 运行期通过 `run(..., runtime_vars={...})` 提供变量。

核心实现：`src/scalim/dsl/by_yaml/params_template.py`。

---

## 4) IR → Plan：required_fields 剪枝的真实口径

规划入口：`src/scalim/planning/builder.py::PlanBuilder.build`

事实点：

- `targets=None` 时默认所有字段；
- `targets=[...]` 时会做依赖闭包，只保留 required_fields；
- 会检测循环依赖并抛 `graph.CyclicDependencyError`；
- 生成 `ExecutionPlan.field_dependencies` 作为执行层 required-fields 的权威口径(避免 `FieldIr.get_dependencies()` 在“主表在右侧”时的错误依赖)。

执行层 required-fields 闭包计算也明确使用 `ExecutionPlan.field_dependencies`：

- `src/scalim/execution/pipeline/base/pipeline.py::Pipeline._compute_required_fields`

---

## 5) Plan → Execution：pipeline 的三条“输出路径”

核心调度：`src/scalim/execution/pipeline/base/pipeline.py::SeqPipeline.run`

### 5.1 普通批量模式(ISink 仅 `write_batch`)

- 若传入 sink 但它不是 `IRowSink/IColumnSink`：走 `BatchExecutor.execute_batch` 返回批次结果，再 `sink.write_batch(...)`
- 若未传入 sink 且 `OutputSpec.path` 为空：execution 编排层默认 `_NullSink`，避免在内存里累积结果列表(见 `src/scalim/execution/run_ir.py::_NullSink`)。

### 5.2 列式流式(IColumnSink)

- 先 `set_row_ids(...)` 再按列写入；
- 每列写完可触发 FieldSlimEvent 并释放列内存；
- 适合宽表(字段很多)。

关键实现：`src/scalim/execution/pipeline/base/pipeline.py::_execute_batch_column_mode`

### 5.3 行式流式(IRowSink)

- 行就绪即写出(`write_row`) + 行/字段释放；
- `bind.mode=rows` 会触发 release 屏障：写出可以发生，但释放会被延后到屏障解除。

关键实现：

- `src/scalim/execution/pipeline/base/pipeline.py::_execute_batch_streaming_mode`
- `src/scalim/execution/pipeline/base/_row_emission.py::RowEmissionCoordinator`

---

## 6) 并发：adaptive 的真实并行边界

事实点(不要误解)：

- `parallel_mode=adaptive` 只并行**批次内**的 `LoadRef` 段；
- `load/compute/write/release` 仍按算子顺序串行；
- 未提供 adaptive pool 时(或退化判定)会回退串行。

入口链路：

- engine 校验：`src/scalim/execution/engine.py`
- segment 执行：`src/scalim/execution/executor/batch/executor.py::_execute_loadref_segment`
- 调度器：`src/scalim/execution/adaptive/loadref_scheduler.py`

---

## 7) 输出组合(outputs)与单输出模式的优先级

YAML 侧 `outputs:` 会在编译期被转换为 execution 的 `ExecutionRequest.output_composition`：

- 编译：`src/scalim/dsl/by_yaml/runtime/compiler.py::build_request`
- 执行装配：`src/scalim/execution/run_ir.py::_assemble_outputs`

关键优先级(高 → 低)：

1. driver 注入 `output_composition=...`(完全覆盖 YAML 的 `outputs`)
2. YAML 声明的 `outputs`
3. 单输出模式 `overrides.output.*` + `OutputSpec`(仅在未启用 outputs 时生效)

---

## 8) 观测/诊断与事件 wants-gated 的事实

InstrumentationHub 是“统一门控点”：

- `src/scalim/ob/hub.py::InstrumentationHub.wants(event_type)`
- 未订阅时不会构造 payload，也不会创建 Event envelope

这点对精简决策的含义：

- 你可以删掉 `frontend/scalim-viz/` UI，而保留 `VizObserver` 输出 artifacts；
- 事件/observer 基础设施仍是 runtime 核心能力之一(大量性能/护栏/调度诊断都走这条通道)。

