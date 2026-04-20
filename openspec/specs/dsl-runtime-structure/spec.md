# dsl-runtime-structure Specification

## Purpose
定义 YAML DSL runtime 作为 DSL adapter/编译器的边界与对外入口，明确 YAML 配置（outputs/可观测性/retry 等）在编译期映射为 DSL-agnostic 运行请求对象的规则。

## Related Concepts
YAML DSL runtime (编译器/适配器)、IR 转换器、阶段边界、统一 IR 执行入口、config_parsing (解析/校验)、schema_dsl (模型)、Workflow 入口

## Requirements

### Requirement: yaml_dsl runtime 是纯 adapter/编译器
系统 MUST 将 yaml_dsl runtime 的职责收敛为 DSL adapter：
- YAML 解析/校验
- allowlist 安全边界（动态引用解析）
- `DemandConfig -> DemandIr` 编译
- 将 `output`/`observability`/`retry` 编译为 DSL-agnostic 的运行请求对象
- 将 execution core result 包装为 YAML wrapper result

yaml_dsl runtime MUST NOT 直接承担执行编排主流程（plan 构建、engine 实例化/调用、sink finalize、observer manager 生命周期），这些 MUST 由 execution 的统一 IR 编排入口负责。

yaml_dsl runtime 同时 MUST NOT 承载 workflow 的执行编排；workflow runtime MUST 位于 framework 层，YAML workflow 入口仅做前端编译与依赖注入。

#### Scenario: runtime 仅作为适配层
- **WHEN** 审阅 YAML DSL 的运行路径
- **THEN** 运行编排应委托 execution 层统一入口，而非在 runtime 内部自行拼装完整执行链

#### Scenario: workflow orchestration is not implemented in yaml_dsl runtime
- **WHEN** 调用方通过 workflow 的稳定入口运行 workflow YAML
- **THEN** workflow 的调度执行与资源/ctx/事件桥接 MUST 由 framework 层实现，而不是 runtime

### Requirement: official facade MUST preserve current extension seams
系统 MUST 保持当前已确认的受控扩展点继续可经由官方 facade 使用，而不是通过删减能力来完成"收敛"。

本轮至少包括：
- `CapturePolicy`（`CaptureNone`/`CaptureRows`）：显式控制是否捕获内存行数据
- `DemandRunRuntimeOptions.components`：demand 执行层的 observers/hooks
- `WorkflowRunOptions.workflow_components`：workflow 编排层的 observers/hooks
- `DemandRunSecurityOptions`：安全边界（allowed_modules/allowed_functions/allowed_yaml_roots）
- `RunOverrides`：输出覆盖、viz 配置等

系统 MUST 保持多输出组合能力为"受控 authoring surface"：由 YAML `outputs/resources` 与 `RunOverrides` 的受控覆盖项表达；官方 facade 不新增通用注入面，避免公共 API 膨胀。

#### Scenario: public facade remains behavior-complete for supported extension seams
- **WHEN** 调用方通过公开 facade 使用受控扩展点（CapturePolicy、components、security、overrides）
- **THEN** 系统 MUST 继续支持这些能力
- **AND** 公共表面收敛 MUST 体现为"入口与契约明确"，而不是静默删除这些受支持能力

### Requirement: YAML DSL 官方入口为 yaml_dsl facade
系统 MUST 将 `yaml_dsl` 作为 YAML DSL 的首选公开 facade，用于承载用户最常见且受支持的运行入口与运行期契约。

该官方入口 MUST 以"受控 re-export"方式提供最小 facade：
- 运行入口：`run` / `compile` / `run_workflow`
- 运行期契约：`UNSET`、`ResolverTrustedMode`、`DemandRunOptions`、`DemandRunResult`、`RunOverrides`、`WorkflowRunOptions`、`Compilation`

#### Scenario: caller can import facade entrypoints and contracts from yaml_dsl
- **WHEN** 调用方从 yaml_dsl 导入 run/compile/run_workflow 和相关契约类型
- **THEN** 导入 MUST 成功且行为与实现一致

### Requirement: entrypoints MUST accept single options object
系统 MUST 将 demand 和 workflow 的运行入口收敛为 options-object 形态：
- demand: `run(yaml_path, *, options: DemandRunOptions)` / `compile(yaml_path, *, options: DemandRunOptions)`
- workflow: `run_workflow(workflow_yaml_path, *, options: WorkflowRunOptions)`

`DemandRunOptions` MUST 作为运行期 knobs 的唯一承载对象（安全边界、模板、并行、重试、护栏、overrides、输出/capture 等）。

`WorkflowRunOptions` MUST：
- 通过 `.demand: DemandRunOptions` 承载节点的 demand 运行期 knobs
- 通过 `.patches_by_run_id` 提供 per-run patch（patch MUST NOT 覆盖安全边界）
- 通过 `.runtime` 承载 workflow-scope 的 runtime policy（execution/scheduler/cache_pool/resources_wait/output_staging）
- 将编排参数（如 path_aliases）收敛在内部，不再以独立 kwargs 形式暴露

#### Scenario: options-object drives compile and run
- **GIVEN** 调用方构造完整的 `DemandRunOptions`
- **WHEN** 调用方执行 `run("path/to/demand.yaml", options=options)`
- **THEN** 系统 MUST 使用该 `DemandRunOptions` 完成加载/编译/执行
- **AND** 运行行为 MUST 与同等配置通过旧入口实现时一致

#### Scenario: workflow entrypoint uses embedded demand options
- **GIVEN** 调用方构造 `WorkflowRunOptions(demand=demand_options, runtime=..., patches_by_run_id={...})`
- **WHEN** 调用方执行 `run_workflow("path/to/workflow.yaml", options=workflow_options)`
- **THEN** 系统 MUST 使用该 `DemandRunOptions` 作为每个 demand run 的 base options
- **AND** per-run patches MUST 在该 base options 上应用

#### Scenario: invalid option combinations are rejected before execution
- **GIVEN** 调用方构造运行入口的 `options` 对象
- **WHEN** `options` 中出现违反安全边界或输出策略约束的非法组合
- **THEN** 系统 MUST 在构造/校验阶段 fail-fast 抛出异常
- **AND** 异常信息 MUST 指向冲突的字段/分组

### Requirement: output capture/write semantics MUST be explicit and consistent
系统 MUST 将"是否落盘/是否保留内存"等选择以显式、强类型的输出策略表达，而不是通过"额外传入一个参数即可隐式改变 sink 行为"的方式组合语义。

系统 MUST 在公开运行入口中移除 `sink`/`return_data` 这类会引入隐式 tee 语义的参数/字段。

系统 MUST 确保 demand 与 workflow 的输出/捕获规则边界一致：相同的输出策略输入在两条入口链路中应得到一致的行为。

#### Scenario: run 不再接受 return_data/sink
- **WHEN** 用户调用 `run(..., return_data=...)` 或 `run(..., sink=...)`
- **THEN** 系统应报错（参数不存在）并提示迁移为显式 capture

#### Scenario: run 支持显式 capture rows
- **WHEN** 用户调用 `run(..., options=DemandRunOptions(outputs=DemandRunOutputOptions(capture=CaptureRows())))`
- **THEN** 系统返回的 `DemandRunResult.captured_rows` MUST 为非空的 `InMemoryRows`

#### Scenario: to_dataframe fail-fast when capture is disabled
- **GIVEN** 调用方未显式启用 capture（保持为 `CaptureNone`）
- **WHEN** 调用方调用 `DemandRunResult.to_dataframe()`
- **THEN** 系统 MUST fail-fast 并给出如何启用 capture 的指引

### Requirement: YAML `outputs` MUST compile into DSL-agnostic output request
系统 MUST 将 YAML `outputs`（以及 `overrides.outputs`）编译为 execution 层的输出编排请求对象，并确保 execution/engine 不需要读取 YAML config 即可完成写出。

系统 MUST 使用 `overrides.outputs` 作为输出覆盖的唯一形态，并破坏性移除历史 `overrides.output.*`。

`overrides.outputs` 的语义 MUST 为"整体替换"（replace）：当其提供且非空时，系统 MUST 仅使用 `overrides.outputs` 作为 effective outputs，而不是对 YAML `outputs` 做 deep-merge。

当调用方显式提供 `overrides.outputs=[]` 时，系统 MUST fail-fast（避免静默"不导出任何东西"）。

#### Scenario: execution does not read YAML config for outputs
- **WHEN** 调用方通过 adapter 编译得到 execution request 并执行
- **THEN** execution/engine MUST 仅依赖编译产物中的输出编排对象完成写出

#### Scenario: overrides 覆盖 outputs
- **GIVEN** YAML 配置包含 `outputs`
- **WHEN** 调用方提供 `overrides.outputs`
- **THEN** adapter 编译产出的输出编排 MUST 反映 `overrides.outputs` 的覆盖结果

#### Scenario: 缺省 outputs 时使用默认策略且 overrides 仍生效
- **WHEN** YAML 配置未声明顶层 `outputs` 且调用方在 `compile/run` 中提供 `overrides.outputs`
- **THEN** adapter 编译产出的 effective outputs MUST 等于 `overrides.outputs`
- **AND** 当两者都缺省时，MUST 使用 execution 层的默认输出策略

### Requirement: DSL 返回 wrapper(core 为 ExecutionResult)
系统 MUST 使 execution 返回 DSL-agnostic 的 `ExecutionResult`，并使 YAML 运行入口返回 YAML wrapper result（例如 `DemandRunResult`）以承载 YAML-only 元信息并包含/引用 core result。

#### Scenario: execution 不依赖 YAML result 类型
- **WHEN** 另一个 DSL 已产出 `DemandIr` 并调用 execution 统一入口
- **THEN** 它应获得同一个 `ExecutionResult` 结构，不需要依赖 YAML wrapper/result 类型

### Requirement: Allowlist 安全语义保持
系统 MUST 继续要求显式 allowlist 才能执行 YAML 中的 Python 引用，并在 allowlist 缺失或为空时抛出 `AllowlistRequiredError`（或等价错误）。

对外 API 合约 MUST 与该安全语义对齐：
- `DemandRunSecurityOptions.allowed_modules` MUST 为必填字段（类型上去 `Optional`）
- `DemandRunOptions.security` MUST 为必填字段，且 `run/compile` 入口不得隐式设置 allowlist

#### Scenario: 未提供 allowlist 或 allowlist 为空
- **WHEN** 调用方构造 `DemandRunSecurityOptions(allowed_modules=frozenset())` 且未提供有效的 `allowed_functions`
- **THEN** 系统 MUST 抛出 `AllowlistRequiredError`

#### Scenario: workflow patch 不得覆盖安全边界
- **GIVEN** 调用方为某个 run_id 提供 patch
- **WHEN** patch 尝试覆盖 allowlist/trusted mode 等安全边界字段
- **THEN** 系统 MUST fail-fast 拒绝该 patch

### Requirement: 可观测集成由 runtime entrypoints 承载
系统 SHALL 将可观测性视为 runtime integration surface：
- YAML DSL MUST NOT 将 `observability:` 作为稳定 authoring surface（legacy key 可 warning + ignore 作为迁移过渡）
- 运行入口 SHOULD 通过 typed runtime entrypoints（components/viz_config）承载装配
- 不得引入与上述装配面并列的零散 bool 开关（例如单独的 `use_memory_hook` 或 `pretty_logging`）

#### Scenario: 通过 runtime entrypoints 启用可观测性
- **WHEN** 用户希望启用内存/CPU/性能/可视化等观测能力
- **THEN** 用户应通过 components / viz_config 完成装配，无需额外 bool 开关

### Requirement: runtime 编译链路必须按阶段边界组织
系统 MUST 将 yaml_dsl runtime 的主链路明确为"解析/校验/编译/运行请求映射"四段边界，并以显式契约对象连接各阶段。

系统 MUST 保持该边界可测试，不允许在单一阶段函数中混合多阶段职责。

编译链路 API MUST 包括：load_config、compile_ir、build_request。

stage API MUST 包括：stage_validate_allowlist、stage_create_context、stage_load_yaml_config、stage_compile_demand_ir、stage_build_execution_request。

#### Scenario: 编译链路职责边界可被独立验证
- **WHEN** 审阅 runtime 编译链路对应模块
- **THEN** 每一阶段 MUST 具有独立输入输出契约
- **AND** 行为回归测试 MUST 能单独覆盖阶段边界

### Requirement: 模块按职责拆分且保持稳定入口
系统 MUST 将 yaml_dsl runtime 及相关模块按职责拆分为子包/子模块，并保持稳定可导入的入口。

相关模块包括但不限于：
- `runtime/` 子包（从 legacy 单文件模块拆分）
- `schema_dsl/` 模型（按领域拆分 source/field/output/observability 等）
- `config_parsing/` 子模块（解析/校验/安全/索引逻辑）
- 热点模块（如 `config_parsing/validators/fields.py`、`runtime/conversion.py`）

系统 SHOULD 避免在包根重导出大量符号，调用方 SHOULD 从显式子模块导入所需符号。

#### Scenario: 显式导入入口可用
- **WHEN** 使用显式导入路径从 entrypoints/introspection/conversion 等子模块导入
- **THEN** 可正常导入且行为一致

#### Scenario: 仅新命名可导入
- **WHEN** 调用方尝试从旧入口导入旧命名或从旧模块入口导入
- **THEN** 导入 MUST 失败

#### Scenario: 模块拆分后入口保持兼容
- **WHEN** 调用方从模型入口路径导入 schema 相关类型
- **THEN** 导入 MUST 成功
- **AND** 不需要调用方感知内部文件拆分细节

#### Scenario: 子模块导入可用且运行行为不变
- **WHEN** 使用 config_parsing.loader/validator 导入或使用既有运行入口执行 YAML
- **THEN** 导入/输出/错误语义与拆分前保持一致

#### Scenario: fields validator 拆分后稳定入口保持
- **WHEN** 维护者拆分 fields validator
- **THEN** 调用方通过 validator 的既有关键类型导入 MUST 继续成功
- **AND** YAML 校验输出与错误语义 MUST 与重构前保持等价

#### Scenario: conversion 拆分后编译链路边界清晰
- **WHEN** 维护者重构 conversion 模块
- **THEN** Config→IR 转换、运行请求映射与辅助逻辑 MUST 具备可独立验证的边界
- **AND** 现有 YAML runtime 入口行为 MUST 与重构前保持一致

### Requirement: 动态解析边界收敛
系统 MUST 将动态引用解析（`importlib`/反射访问）集中在明确的解析边界，其它逻辑仅通过显式字段/结构访问数据。

#### Scenario: 转换阶段不使用反射
- **WHEN** 执行 Config→IR 转换流程
- **THEN** 不依赖字符串拼接或 `getattr/hasattr/setattr` 访问

### Requirement: YAML 特定配置编译为 DSL-agnostic execution request
系统 MUST 在 yaml_dsl runtime 编译期将 YAML 的特定配置（如 batch_size、retry、template_vars 等）编译为 DSL-agnostic 的 execution request 字段，并在执行期由 execution 层统一消费。

编译规则：
- `batch_size` MUST 编译为 `ExecutionRequest.batch_size: Optional[int]`，保持 `None` 语义可穿透 execution，MUST NOT 使用 truthy fallback
- `retry` 配置 MUST 编译为 loader retry policy 字段
- `template_vars`/`init_vars` MUST 在 YAML parse 前完成预编译，确保 `DemandIr` 内持有的静态 params 可包含初始化对象

当调用方在 runtime/driver 层显式注入策略时，其优先级 MUST 高于 YAML 中的配置（与 guardrails 的覆盖语义一致）。

#### Scenario: explicit None disables chunking and skips policy signal
- **WHEN** 调用方显式传入 `batch_size=None`
- **THEN** 编译产出的 `ExecutionRequest.batch_size` MUST 为 `None`
- **AND** 系统 MUST 跳过 `pre_use_batch_size` policy signal

#### Scenario: policy signal override batch_size when UNSET
- **GIVEN** 调用方未显式提供 `batch_size`（保持为 `UNSET`）
- **WHEN** 某个 hook 在 `pre_use_batch_size` signal 中将候选值改写为 `20000`
- **THEN** 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `20000`

#### Scenario: YAML retry 缺省时 request 不启用 retry
- **WHEN** YAML 未声明任何 `retry`
- **THEN** 编译产出的 execution request MUST 不启用 loader retry（等价于 disabled）

#### Scenario: driver 覆盖 YAML retry
- **GIVEN** YAML 中声明 `retry.max_attempts=3`
- **WHEN** 调用方显式注入 policy 且 `max_attempts=5`
- **THEN** effective policy MUST 使用 `max_attempts=5`

#### Scenario: compile 接收 template_vars 并预编译 YAML
- **GIVEN** YAML 文本包含 LiteJinja2 模板语法 `{{ ... }}`
- **WHEN** 调用方执行 `compile(..., options=DemandRunOptions(template=DemandRunTemplateOptions(template_vars={...})))`
- **THEN** adapter MUST 在 YAML parse 前完成预编译
- **AND** 后续编译链路 MUST 基于预编译后的配置继续执行

#### Scenario: 编译期完成 init_vars 占位符解析
- **WHEN** 调用方执行 `compile(..., options=DemandRunOptions(template=DemandRunTemplateOptions(init_vars=...)))`
- **THEN** adapter 返回的 `Compilation.demand_ir` MUST 已反映占位符解析后的 params 值
- **AND** execution 层不需要再做二次解析

### Requirement: public workflow facade MUST NOT expose injection/test-only knobs
系统 MUST 收口 workflow 入口的 public surface：公共 facade MUST NOT 暴露注入型/测试专用参数（例如 `run_ir_fn` / `compile_demand_yaml_fn`），且这些注入点也 MUST NOT 出现在公开 options 对象中。

若框架内部仍需要这些注入点，系统 MUST 将其放置在 internal/test-only 边界，避免用户材料固化内部实现结构。

#### Scenario: passing injection knobs to public facade fails fast
- **WHEN** 调用方对公共 facade 传入 `run_ir_fn` 或 `compile_demand_yaml_fn`
- **THEN** 该调用 MUST 失败（参数不存在或被拒绝）
- **AND** 错误信息 SHOULD 指向 internal/test-only 注入入口或迁移方式
