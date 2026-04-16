# execution-structure Specification

**状态: ✅ 已实现**
## Purpose
定义 execution 层的模块拆分与入口契约,并明确统一 IR 编排入口(如 `run_ir`)的边界,确保执行编排对 DSL 配置解耦且行为在重构后保持兼容.
## Related Code (as implemented)
- `src/IMPL_ROOT/execution/run_ir.py` (`run_ir` + DSL-agnostic request/result models)
- `src/IMPL_ROOT/execution/engine.py` (`ScalesEngine`)
- `src/IMPL_ROOT/execution/pipeline/base/pipeline.py` (`SeqPipeline` orchestration)
- `src/IMPL_ROOT/execution/pipeline/overrides.py` (`PipelineOverrides`)
- `src/IMPL_ROOT/execution/adaptive/config.py` (shared adaptive config resolver)
- `src/IMPL_ROOT/execution/executor/batch/executor.py` (`BatchExecutor`)
- `src/IMPL_ROOT/ob/components.py` (`split_components`)
- `src/IMPL_ROOT/ob/observability.py` (`Observability.build_manager`)

## Implementation Notes (Current Behavior)
- `run_ir(...)` 当前在 execution 侧内部完成 `PlanBuilder(demand_ir).build(targets=...)`(不接受外部预构建 plan 注入).
- `OutputSpec.path` 为 falsy 时不会创建文件 sink;当其为相对路径时以运行时进程 CWD 为基准;会自动创建父目录(`mkdir(parents=True, exist_ok=True)`)并可能覆盖同名文件;当 file sink 与自定义 `sink` 同时存在时,会尝试 tee(要求 row/column sink 类型一致,否则抛出带迁移提示的错误).
- `ExecutionRequest.components` 通过 `split_components` 拆成 observers/hooks,分别注册到 `ObserverManager` 与 `HookManager`;`viz_config` 存在时会基于 plan 注册 `VizObserver.from_plan(...)`.
- `ExecutionResult.total_rows` 统计口径为“实际写入 effective sink 的行数”(由 sink wrapper 计数),与部分 observability 指标的输入行计数口径不同.
- `ScalesEngine` 实例不应被并发复用;当前实现会在单个 engine 实例内序列化 `run()` 调用以避免共享 runtime/caches 的并发竞态.
## Requirements
### Requirement: execution 提供统一 IR 编排入口并返回通用结果
系统 MUST 在 execution 层提供统一 IR 执行编排入口(概念名: `run_ir`,具体模块/符号名可调整),负责:
- 基于 `DemandIr` + `ExecutionRequest` 构建 plan
- 装配 sinks/observers/hooks 并完成收尾
- 调用 engine 执行并产出 **DSL-agnostic** 的 `ExecutionResult`

该入口 MUST 不依赖任何 DSL 专有配置类型(例如 YAML 的 `DemandConfig`/`ObservabilityConfig`).

#### Scenario: YAML 通过 execution 入口执行
- **WHEN** YAML adapter 运行 YAML DSL
- **THEN** 它应调用 execution 统一 IR 编排入口完成执行,而非在 DSL 层自行编排

#### Scenario: 多 DSL 复用 execution 入口
- **WHEN** 另一个 DSL 适配层已产出 `DemandIr`
- **THEN** 可直接复用 execution 统一 IR 编排入口并获得同一个 `ExecutionResult` 结构

### Requirement: execution Tier1 facade MUST expose an options-only `run_ir` entrypoint
系统 MUST 将 execution 层的统一编排入口（`run_ir`）与其 DSL-agnostic contracts（`ExecutionRequest`/`ExecutionResult` 等）作为官方推荐 public facade 的一部分,
确保用户材料无需引用内部模块路径即可完成执行编排.

该 facade MUST 满足：

- `scalim.execution` MUST 提供 `run_ir` 与 `ExecutionRequest` 的稳定导入路径（通过 re-export 或等价方式）。
- 调用入口 MUST 以单一 request/options 对象驱动（`ExecutionRequest` 为唯一运行期契约承载）。

#### Scenario: user imports and runs execution via curated facade
- **WHEN** 调用方执行 `from scalim.execution import ExecutionRequest, run_ir`
- **THEN** 导入 MUST 成功
- **AND** 调用方 MUST 能以 `run_ir(demand_ir, request=ExecutionRequest(...))` 的方式运行而无需导入 `scalim.execution.run_ir` 模块路径

### Requirement: `ExecutionRequest`/`ExecutionResult` 不得包含 DSL config types
系统 MUST 保持 execution 侧的请求/结果对象为 DSL-agnostic:
- 请求中不得直接携带 `DemandConfig`/`ObservabilityConfig` 等 DSL config
- 结果中不得强制暴露 DSL config(DSL wrapper 可自行附加)

#### Scenario: execution 边界清晰
- **WHEN** 审阅 execution 模块的 imports 与类型签名
- **THEN** 不应出现对 DSL config 包的依赖

### Requirement: `run_ir` 模块默认导出面收敛
系统 MUST 将 `IMPL_ROOT.execution.run_ir.__all__` 视为稳定的公开符号集合,并避免将纯内部辅助类型纳入默认导出面.

内部辅助类型可以继续作为模块属性存在(以保持兼容),但 MUST NOT 被加入到 `__all__` 里(避免被 `from ... import *` 视为公开 API).

#### Scenario: `InternalStatsCollector` 不在 `__all__` 中
- **WHEN** 导入 `IMPL_ROOT.execution.run_ir` 并读取其 `__all__`
- **THEN** `__all__` MUST NOT 包含 `"InternalStatsCollector"`

### Requirement: 执行层入口与行为一致
系统 MUST 在执行层重构或拆分后保持对外行为一致,并避免将 `executor`/`pipeline` 的内部模块组织与 `__init__` re-export 作为稳定契约.
调用方应优先通过 `run_ir` 与 `ScalesEngine` 等稳定入口完成执行;内部实现可按最小风险渐进调整.
模块拆分与内部入口约定详见 `module-organization`.

#### Scenario: 既有入口保持稳定
- **WHEN** 使用 `run_ir` 或 `ScalesEngine` 完成执行
- **THEN** 行为保持一致

### Requirement: ScalesEngine API 保持稳定
系统 MUST 保持 `ScalesEngine` 构造参数与 `run` 行为兼容,并允许通过显式 overrides/config 注入 `adaptive` 的 tuning/policy,而不改变默认 `seq` 行为.
未提供 tuning/policy 时,`adaptive` MUST 使用安全默认值.

同时,`batch_size` 的执行语义 MUST 与 YAML/runtime 编译链路统一:
- `batch_size` 允许 `None` 或整数且 `>=1`.
- `batch_size=None` 表示 no-chunking(单批执行).
- `batch_size=<int>=1` 表示固定分批.
- `batch_size` 为 `0`、负数、布尔值、浮点数、字符串等非法输入 MUST 被拒绝,不得通过宽松转换静默修正.

#### Scenario: 旧构造方式仍可用
- **WHEN** 使用 `ScalesEngine(demand, plan, hook_manager=..., batch_size=...)` 创建实例并 `run()`
- **THEN** 除 `batch_size` 语义明确化外,行为与当前版本一致

#### Scenario: batch_size 为 null 时单批执行
- **WHEN** 使用 `ScalesEngine(..., batch_size=None)` 运行
- **THEN** 执行层 MUST 以单批方式处理全部 main rows

#### Scenario: 非法 batch_size 直接失败
- **WHEN** 使用 `batch_size=0` 或 `batch_size=-1` 或 `batch_size=True` 或 `batch_size=1.5` 或 `batch_size=\"oops\"`
- **THEN** 构造或执行 MUST 抛出参数错误并指向 `batch_size`

#### Scenario: adaptive 注入 tuning/policy
- **WHEN** 使用 `ScalesEngine(..., parallel_mode=\"adaptive\", pipeline_overrides=overrides)` 且 overrides 包含 tuning/policy
- **THEN** 执行 MUST 按 tuning/policy 的限流与阈值策略调度并发任务

#### Scenario: 启用 guardrails
- **WHEN** 使用 `ScalesEngine(..., guardrails=policy)` 并运行
- **THEN** pipeline(seq/adaptive)按 guardrails 配置执行

### Requirement: 执行结果与事件顺序一致
系统 MUST 在重构后保持执行输出与 hook 事件顺序不变(相同输入、相同计划与 sink).
当 `parallel_mode=adaptive` 启用批次内并发时,系统 MUST 保持默认结果提交顺序与计划顺序一致,并使事件回放顺序与该提交顺序一致.

#### Scenario: 顺序管线一致性
- **WHEN** 使用相同 plan 与输入运行 `SeqPipeline`
- **THEN** 输出数据与事件顺序保持一致

#### Scenario: adaptive 完成乱序但提交有序
- **WHEN** `parallel_mode=adaptive` 下并发任务完成顺序与提交顺序不一致
- **THEN** 输出结果与事件回放顺序仍应按提交顺序保持一致

### Requirement: adaptive 调度链路必须职责分离
系统 MUST 将 adaptive 执行链路中的策略解析、任务提交、结果聚合职责分离为独立协作单元,并通过显式接口进行连接.
系统 MUST NOT 由单一调度器实现同时长期承载上述全部职责.

#### Scenario: 调度器重构后行为保持等价
- **WHEN** 在 adaptive 路径重构调度器内部结构
- **THEN** 相同输入下输出顺序、事件顺序与错误语义 MUST 与重构前一致
- **AND** 调度策略解析路径 MUST 可独立测试

#### Scenario: 调度协作单元可替换
- **WHEN** 维护者需要替换某一调度子策略
- **THEN** 应仅替换对应协作单元
- **AND** 不需要修改提交器与聚合器的核心实现

### Requirement: execution 内部扩展点必须通过显式 seam 暴露
系统 MUST 通过 overrides/config/protocol 等显式 seam 暴露 execution 内部扩展点,MUST NOT 依赖模块级隐式注入或运行时反射 patch 作为长期机制.

#### Scenario: 通过显式 seam 定制执行行为
- **WHEN** 调用方需要定制并发策略或批次执行策略
- **THEN** 调用方 MUST 通过显式 seam 注入
- **AND** 系统 MUST 不要求 monkeypatch 私有模块变量

### Requirement: Pipeline 覆盖点显式化
系统 MUST 将 execution pipeline 的可覆盖实现细节(例如批次切分策略、`adaptive` 的并发调度器/执行器类型)收敛为显式注入的 overrides/config 对象,而不是通过模块级变量与 `sys.modules` 探测实现隐式注入.

#### Scenario: 不依赖模块注入
- **WHEN** 用户希望覆盖批次切分或 `adaptive` 调度器/执行器
- **THEN** 应通过显式 overrides/config 注入完成,且不需要 monkeypatch 模块变量

### Requirement: PlanMetadata.max_depth 反映依赖图的最大层级
系统 MUST 在 `ExecutionPlan.metadata.max_depth` 中提供稳定的最大依赖深度,其值 MUST 等于该执行计划依赖图的最大层级(与 stages 的 level 一致).

#### Scenario: max_depth 等于最大 stage level
- **WHEN** 使用 `PlanBuilder` 构建任意执行计划
- **THEN** `plan.metadata.max_depth` MUST 等于 `max(stage.level for stage in plan.stages)`(无 stages 时为 0)

### Requirement: 字段依赖口径以 `ExecutionPlan.field_dependencies` 为准
系统 MUST 将 `ExecutionPlan.field_dependencies` 视为字段依赖推断的权威来源,其依赖关系 MUST 基于主数据源方向与 lookup steps 推断得出.
`FieldIr.get_dependencies()` 仅为简化 helper(可能在主表位于 relation 右侧时返回错误依赖),执行层的 required-fields 闭包计算与调度 MUST NOT 依赖该方法的结果.

#### Scenario: required-fields 使用 plan 依赖口径
- **WHEN** execution pipeline 计算 required-fields 的传递闭包
- **THEN** 必须使用 `ExecutionPlan.field_dependencies` 的依赖映射
- **AND** 不得使用 `FieldIr.get_dependencies()` 作为依赖推断依据

### Requirement: `ExecutionPlan.operators` 的核心算子边界清晰
系统 MUST 将 `PlanBuilder` 的产出算子集合限定为 planning 核心算子(`load` / `load_ref` / `compute`).
输出写入(例如 `write_column` / `write_row`)与释放(`release`)不由 `PlanBuilder` 生成,且不应被理解为 `ExecutionPlan.operators` 的默认组成部分.

#### Scenario: PlanBuilder 仅生成核心算子类型
- **WHEN** 通过 `PlanBuilder(demand).build(...)` 构建 `ExecutionPlan`
- **THEN** `plan.operators` 中的每个 operator MUST 是 `LoadOperatorIr` / `LoadRefOperatorIr` / `ComputeOperatorIr` 之一
- **AND** 每个 operator 的 `operator_type` MUST 属于 `{"load", "load_ref", "compute"}`

### Requirement: adaptive tuning/policy 解析逻辑集中以避免 drift
当 execution 层需要解析与校验 adaptive 的 policy/tuning/max_workers 时,系统 MUST 优先集中为共享 helper.
当前实现中,pipeline 与 `BatchExecutor` MUST 复用同一共享 helper;`AdaptiveLoadRefScheduler` 允许保留本地解析路径,但其默认值与校验语义应与共享路径保持一致,避免行为漂移.

该集中化 MUST 保持现有行为一致:默认值策略、Python 3.6 的 backend 回退语义、以及错误类型/错误信息口径不变.

#### Scenario: pipeline 与 BatchExecutor 复用同一解析路径
- **WHEN** pipeline 与 `BatchExecutor.execute_operators(...)` 都需要得到已校验的 adaptive tuning 与 worker 数
- **THEN** 它们应通过同一共享 helper 获得一致结果
- **AND** `AdaptiveLoadRefScheduler` 的本地解析实现应保持与该共享路径等价的默认值与校验语义

### Requirement: ExecutionRequest 支持 loader retry policy 且默认关闭
系统 SHALL 在 execution 侧的请求对象(例如 `ExecutionRequest`)中提供可选的 loader retry policy 字段,用于控制所有 loader 调用点的重试行为.
当该字段缺省/disabled 时,系统 MUST 保持现有行为(不重试).

#### Scenario: request 未启用 retry 时行为不变
- **WHEN** `ExecutionRequest` 未配置 loader retry policy(或 `enabled=false`)
- **THEN** 任一 loader 异常 MUST 直接传播并终止执行(与当前版本一致)

### Requirement: loader 调用点必须统一套用 retry runner
系统 MUST 在所有会实际调用用户 loader 的执行热路径中统一应用 retry runner,包括但不限于:
- `load`(非 ref source loader 调用)
- `load_ref`(ref loader 调用,含 lookup_keys 分片/多次调用)
- `preload_forever`(预加载路径)
- main_source loader 的“首次调用”(创建 iterable 的那次调用)

对于 `load_ref` 的分片调用,系统 SHOULD 将每次实际 loader 调用视为独立一次 invocation,并对每次 invocation 单独应用 retry policy(仍受该 policy 的 attempt/elapsed 约束).

#### Scenario: load_ref 分片调用按 invocation 重试
- **GIVEN** `lookup_chunk_size=100` 导致一次 load_ref 被拆为多次 loader 调用
- **WHEN** 其中一片调用抛出瞬态异常且 `should_retry` 返回 true
- **THEN** 系统 MUST 对该片调用执行重试(不要求回滚其它已成功片段)

### Requirement: adaptive scheduler 热点必须进一步拆分为可替换协作单元
系统 MUST 将 `execution/adaptive/loadref_scheduler.py` 视为确认热点,并允许其继续拆分为更清晰的协作单元,至少包括策略/worker 数解析、layer planning、任务提交、结果聚合与提交顺序维护.

#### Scenario: scheduler 拆分后协作单元边界清晰
- **WHEN** 维护者重构 `AdaptiveLoadRefScheduler` 的内部结构
- **THEN** 策略解析、任务提交与结果聚合 MUST 可独立测试
- **AND** 不得要求单一热点调度器长期同时承载上述全部职责

### Requirement: scheduler 热点拆分后输出与事件顺序保持稳定
系统 MUST 在 `loadref_scheduler.py` 拆分后继续保持相同输入下的输出顺序、事件回放顺序与错误语义不变.

#### Scenario: scheduler 结构重构后行为等价
- **WHEN** 完成 adaptive scheduler 的内部职责拆分
- **THEN** 相同输入下的输出顺序、事件顺序与错误语义 MUST 与重构前保持一致

### Requirement: execution contracts MUST be splittable from orchestration while preserving stable entrypoints
系统 MUST 允许将 execution 的 DSL-agnostic contracts(例如 `ExecutionRequest`/`ExecutionResult`)从 orchestration 逻辑中拆分到独立模块,以降低热点文件聚合度并改善可测试性。

同时系统 MUST 保持稳定入口不变:
- 既有 `run_ir` 稳定导入路径 MUST 继续可用
- contracts 在稳定入口处的导入路径 MUST 继续可用(可通过 re-export 兼容)

#### Scenario: existing run_ir imports remain stable after refactor
- **WHEN** 调用方通过既有稳定入口导入并调用 `run_ir`
- **THEN** 导入 MUST 成功且行为与重构前一致
