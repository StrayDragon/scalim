# dsl-runtime-structure Specification

**状态: ✅ 已实现**
## Purpose
定义 by_yaml runtime 作为 DSL adapter/编译器的边界与对外入口,并明确 YAML `output`/`observability` 在编译期映射为 DSL-agnostic 运行请求对象的规则.
## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/entrypoints.py` (`run`, `compile`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/compiler.py` (`load_config`, `compile_ir`, `build_request`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/contracts.py` (`RunOptions`, `RunOverrides`, `RunResult`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py` (`ConfigToIRConverter`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/introspection.py` (`resolve_required_field_ids`, `build_viz_observer`, `load_output_config`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/stages.py` (stage boundaries)
- `src/IMPL_ROOT/execution/run_ir.py` (unified IR execution entrypoint)
## Requirements
### Requirement: by_yaml runtime 是纯 adapter/编译器
系统 MUST 将 `IMPL_ROOT.dsl.by_yaml.runtime`(以及其对外入口)的职责收敛为 DSL adapter:
- YAML 解析/校验
- allowlist 安全边界(动态引用解析)
- `DemandConfig -> DemandIr` 编译
- 将 `output`/`observability` 编译为 DSL-agnostic 的运行请求对象
- 将 execution core result 包装为 YAML wrapper result

by_yaml runtime MUST NOT 直接承担执行编排主流程(如 plan 构建、engine 实例化/调用、sink finalize、observer manager 生命周期),这些 MUST 由 execution 的统一 IR 编排入口负责.

#### Scenario: runtime 仅作为适配层
- **WHEN** 审阅 YAML DSL 的运行路径
- **THEN** 运行编排应委托 execution 层统一入口,而非在 by_yaml/runtime 内部自行拼装完整执行链

### Requirement: by_yaml runtime compiles `runtime_vars` into loader params templates
系统 SHALL 扩展 by_yaml runtime 的对外入口 `run/compile` 与 `RunOptions`,允许调用方提供可选的 `runtime_vars` 用于 loader 参数模板注入.
adapter MUST 在 `DemandConfig -> DemandIr` 转换前完成 `$runtime.*` 占位符解析,以确保:
- `DemandIr` 内持有的静态 params 可包含运行期对象(例如 `datetime`)
- execution 层无需理解 `$runtime.*` 语法
- preload 与 ref loader 共用同一份编译后的 params template representation,而不是各自维护一套 params 透传逻辑

#### Scenario: 编译期完成占位符解析
- **WHEN** 调用方执行 `compile(..., runtime_vars=...)`
- **THEN** adapter 返回的 `Compilation.demand_ir` MUST 已反映占位符解析后的 params 值
- **AND** execution 层不需要再做二次解析

### Requirement: `output.fields` 的双重语义必须在编译期拆解
系统 MUST 将 YAML `output.fields` 在 adapter 编译期拆解为:
1) 有序 targets(导出字段与顺序)
2) 字段 override(如覆盖 `name`),其效果 MUST 体现在 effective Field IR 上

#### Scenario: output.fields 同时决定顺序与覆盖
- **WHEN** `output.fields` 中包含 `{field_id: order_id, name: 订单ID}` 之类条目
- **THEN** 执行 targets 的顺序与 IR 字段的 `name` 都应反映该编译结果

### Requirement: YAML `output` 编译为 `OutputSpec + ExportLayout`
系统 MUST 将 `output` 的 I/O 策略与布局策略编译为两个 DSL-agnostic 对象并随请求下传:
- `OutputSpec`: format/path/encoding/streaming/include_header 等 I/O 策略
- `ExportLayout`: targets(field_ids) + header_names(若需要)

execution/engine MUST NOT 直接读取 `DemandConfig` 来决定输出格式/路径/表头等策略.

#### Scenario: header_fields_output_by 不穿透到 execution
- **WHEN** YAML 配置 `output.header_fields_output_by: name`
- **THEN** adapter 应产出对齐的 `ExportLayout.header_names`,execution 无需读取 YAML config 即可完成导出

### Requirement: runtime 支持 overrides 覆盖 YAML `output`
系统 SHALL 允许调用方在不修改 YAML 文件的情况下以**显式 overrides** 覆盖 YAML `output` 的部分行为,以适配不同运行环境(例如临时输出路径、不同导出字段顺序).
overrides MUST 是 mask 语义: 未显式设置的字段不覆盖 YAML.

建议 overrides 形态接近 YAML 结构(例如 `overrides.output.path` / `overrides.output.fields`),并允许:
- `overrides.output.path=None` 显式禁用文件输出(即使 YAML 中配置了 `output.path`)
- `overrides.output.fields=[...]` 覆盖 targets/顺序(不改变 YAML 语法)

#### Scenario: overrides 覆盖 output.path 与 fields
- **WHEN** YAML 配置包含 `output.path`/`output.fields`
- **AND** 调用方提供 `overrides.output.path` 或 `overrides.output.fields`
- **THEN** adapter 编译产出的 `OutputSpec.path` 与 `ExportLayout.field_ids` MUST 反映 overrides 的覆盖结果

### Requirement: YAML 缺省 output 时使用默认输出策略且 overrides 仍生效
系统 MUST 允许 YAML DSL 配置缺省顶层 `output` 节点.
当 `output` 缺省时,by_yaml runtime adapter MUST 以 execution 层的默认 `OutputSpec` 作为基线(例如默认 `format: csv`,默认不写文件),并在调用方提供 `overrides.output.*` 时仍然正确应用覆盖.

#### Scenario: 缺省 output 但覆盖 output.path
- **WHEN** YAML 配置未声明顶层 `output`
- **AND** 调用方在 `compile/run` 中提供 `overrides.output.path="..."`
- **THEN** adapter 编译产出的 `ExecutionRequest.output.path` MUST 等于 overrides 指定的路径
- **AND** 其它未覆盖字段(例如 `format`) MUST 保持默认值或来自 YAML 的值(若 YAML 声明了对应字段)

#### Scenario: 缺省 output 且无 overrides
- **WHEN** YAML 配置未声明顶层 `output`
- **AND** 调用方未提供 `overrides.output.*`
- **THEN** adapter 编译产出的 `ExecutionRequest.output` MUST 仍为合法默认值(例如默认 `format: csv`)
- **AND** `ExecutionRequest.output.path` MUST 为空值(不写文件输出)

### Requirement: run 移除 return_data 并支持显式 sink
系统 MUST 破坏性移除对外运行入口中的 `return_data: Optional[bool]`(及其隐式推断/tee 逻辑),
并支持通过显式 `sink=...` 表达是否在内存中保留数据.

#### Scenario: run 不再接受 return_data
- **WHEN** 用户调用 `run(..., return_data=...)`
- **THEN** 系统应报错(参数不存在)并提示迁移为显式 sink(例如 `InMemoryRowSink`)

#### Scenario: run 支持显式 sink
- **WHEN** 用户调用 `run(..., sink=InMemoryRowSink())`
- **THEN** 系统应将结果写入该 sink 且用户可通过 sink 获取数据

### Requirement: DSL 返回 wrapper(core 为 `ExecutionResult`)
系统 MUST 使 execution 返回 DSL-agnostic 的 `ExecutionResult`,并使 YAML 运行入口返回 YAML wrapper result(例如 `RunResult`)以承载 YAML-only 元信息并包含/引用 core result.

#### Scenario: execution 不依赖 YAML result 类型
- **WHEN** 另一个 DSL 已产出 `DemandIr` 并调用 execution 统一入口
- **THEN** 它应获得同一个 `ExecutionResult` 结构,不需要依赖 YAML wrapper/result 类型

### Requirement: YAML DSL 官方入口为 `IMPL_ROOT.dsl.by_yaml`
系统 MUST 提供 `IMPL_ROOT.dsl.by_yaml` 作为 YAML DSL 的官方入口(导入路径),用于承载调用方最常用的稳定接口.

该官方入口 MUST 以“受控 re-export”方式提供最小 facade,并 MUST 导出以下符号:
- 运行入口: `run` 与 `compile`
- 运行期契约: `UNSET`、`OutputOverrides`、`RunOverrides`、`RunOptions`、`Compilation`、`RunResult`

该官方入口 MUST 保持精简:
- MUST NOT 通过包根 re-export `schema_dsl`、`config_parsing` 等大域对象或内部实现细节.
- MUST 通过显式 `__all__` 白名单限制导出面,避免公共 API 膨胀.

#### Scenario: 调用方可通过 IMPL_ROOT.dsl.by_yaml 导入运行入口与 overrides 契约
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.by_yaml import run, compile`
- **AND** 调用方执行 `from IMPL_ROOT.dsl.by_yaml import RunOverrides, OutputOverrides`
- **THEN** 导入 MUST 成功且行为与现有实现一致

### Requirement: runtime 子包化且入口明确
系统 MUST 将 by_yaml runtime 从 legacy 单文件模块 `src/IMPL_ROOT/dsl/by_yaml/runtime.py`(已移除)拆为 `src/IMPL_ROOT/dsl/by_yaml/runtime/` 子包,并提供明确且可维护的入口模块(例如 `entrypoints`/`contracts`/`introspection`).

系统 SHOULD 避免在 `IMPL_ROOT.dsl.by_yaml.runtime`(包根)重导出大量符号:API 尚在演进,过多 re-export 会导致 import-time 成本与循环依赖风险,也容易误导调用方把包根当作“稳定 API”.

调用方 SHOULD 从显式子模块导入所需符号:
- 运行/编译入口:`from IMPL_ROOT.dsl.by_yaml.runtime.entrypoints import run, compile`
- introspection 入口:`from IMPL_ROOT.dsl.by_yaml.runtime.introspection import resolve_required_field_ids, build_viz_observer, load_output_config`
- overrides/结果契约类型:`from IMPL_ROOT.dsl.by_yaml.runtime.contracts import RunOverrides, OutputOverrides, RunResult`

公开编译链路 API(位于 `IMPL_ROOT.dsl.by_yaml.runtime.compiler`)MUST 为:
- `load_config`
- `compile_ir`
- `build_request`

stage API(位于 `IMPL_ROOT.dsl.by_yaml.runtime.stages`)MUST 为:
- `stage_validate_allowlist`
- `stage_create_context`
- `stage_load_yaml_config`
- `stage_compile_demand_ir`
- `stage_build_execution_request`
- `YamlDslStageContext`
- `StageAllowlistMismatchError`

旧命名(例如 `run_yaml`、`parse_yaml_dsl`、`run_stage_*`、`types`、`inspect`)MUST NOT 再作为公开 API 提供.

#### Scenario: 显式导入入口可用
- **WHEN** 使用 `from IMPL_ROOT.dsl.by_yaml.runtime.entrypoints import run, compile`
- **AND** 使用 `from IMPL_ROOT.dsl.by_yaml.runtime.introspection import load_output_config`
- **AND** 使用 `from IMPL_ROOT.dsl.by_yaml.runtime.conversion import ConfigToIRConverter`
- **THEN** 可正常导入且行为一致

#### Scenario: 仅新命名可导入
- **WHEN** 调用方尝试从旧入口导入 `run_yaml`/`YamlDSLOverlay`/`OutputOverlay`/`load_yaml_export_config`(例如 `from IMPL_ROOT.dsl.by_yaml.runtime.api import run_yaml`)
- **OR** 调用方尝试从旧模块入口导入 `IMPL_ROOT.dsl.by_yaml.runtime.types`/`IMPL_ROOT.dsl.by_yaml.runtime.inspect`
- **THEN** 导入 MUST 失败

#### Scenario: 无兼容别名
- **WHEN** 审阅 runtime 公开模块
- **THEN** 不应存在将旧命名转发到新命名的兼容别名或 shim

### Requirement: schema_dsl 模型必须域内拆分且对外入口稳定
系统 MUST 将 by_yaml `schema_dsl` 的模型按领域拆分(例如 source/field/output/observability 等),并保持模型入口的稳定可导入性.
系统 MUST NOT 依赖单个超大模型文件作为长期承载点.

#### Scenario: 模型拆分后入口保持兼容
- **WHEN** 调用方从模型入口路径导入 schema 相关类型
- **THEN** 导入 MUST 成功
- **AND** 不需要调用方感知内部文件拆分细节

#### Scenario: 新增 schema 字段按领域落位
- **WHEN** 新增 YAML DSL schema 字段
- **THEN** 字段定义 MUST 落在对应领域子模块
- **AND** MUST NOT 继续将全部新增字段堆叠到单一聚合文件

### Requirement: by_yaml runtime 编译链路必须按阶段边界组织
系统 MUST 将 by_yaml runtime 的主链路明确为“解析/校验/编译/运行请求映射”四段边界,并以显式契约对象连接各阶段.
系统 MUST 保持该边界可测试,不允许在单一阶段函数中混合多阶段职责.

#### Scenario: 编译链路职责边界可被独立验证
- **WHEN** 审阅 runtime 编译链路对应模块
- **THEN** 每一阶段 MUST 具有独立输入输出契约
- **AND** 行为回归测试 MUST 能单独覆盖阶段边界

### Requirement: config_parsing 子模块化且行为保持
系统 MUST 将 YAML DSL 的解析/校验/安全/索引逻辑拆分到 `config_parsing` 子模块中,并保持运行行为一致.

#### Scenario: 子模块导入可用
- **WHEN** 使用 `from IMPL_ROOT.dsl.by_yaml.config_parsing.loader import YamlDemandLoader`
- **THEN** 可正常导入且行为一致

#### Scenario: 运行行为不变
- **WHEN** 使用既有运行入口执行 YAML
- **THEN** 输出与错误语义保持一致

### Requirement: config_parsing loader/validator 的稳定导出面
系统 MUST 保持 `IMPL_ROOT.dsl.by_yaml.config_parsing.loader` 与 `IMPL_ROOT.dsl.by_yaml.config_parsing.validator` 的稳定导出面:调用方可从明确路径导入下列符号,且行为稳定(模块内部可按领域拆分):

- `YamlDemandLoader`
- `ParsedFieldsResult`
- `ConfigValidator`
- `ValidationIssue`
- `ValidationReport`

#### Scenario: 既有导入路径保持可用
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.by_yaml.config_parsing.loader import YamlDemandLoader`
- **THEN** 导入 MUST 成功且运行行为与拆分前一致

#### Scenario: validator 关键类型可导入
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.by_yaml.config_parsing.validator import ConfigValidator, ValidationReport`
- **THEN** 导入 MUST 成功且校验行为与拆分前一致

### Requirement: Allowlist 安全语义保持
系统 MUST 继续要求显式 allowlist 才能执行 YAML 中的 Python 引用,并在 allowlist 缺失或为空时抛出 `AllowlistRequiredError`(或等价错误).

对外 API 合约 MUST 与该安全语义对齐:
- `RunOptions.allowed_modules` MUST 为必填字段(类型上去 `Optional`).
- `run`/inspect 入口 MUST 要求显式传入 allowlist 参数,且不得默认为 `None`.

#### Scenario: 未提供 allowlist 或 allowlist 为空
- **WHEN** 调用 `run` 且 allowlist 缺失或为空(例如 `allowed_modules=None` 或 `allowed_modules=frozenset()` 且未提供有效的 `allowed_functions`)
- **THEN** 系统 MUST 抛出 `AllowlistRequiredError`

### Requirement: 动态解析边界收敛
系统 MUST 将动态引用解析(`importlib`/反射访问)集中在明确的解析边界(模块命名可调整),其它逻辑仅通过显式字段/结构访问数据.

#### Scenario: 转换阶段不使用反射
- **WHEN** 执行 Config→IR 转换流程
- **THEN** 不依赖字符串拼接或 `getattr/hasattr/setattr` 访问

### Requirement: 可观测配置为唯一 DSL 入口
系统 SHALL 将 YAML DSL 的 `observability:` 作为启用内置可观测能力的唯一配置入口,并避免出现与其并列的额外开关(例如单独的 `use_memory_hook`).

#### Scenario: 无额外开关
- **WHEN** 用户希望启用内存/CPU/性能/可视化等观测能力
- **THEN** 用户应仅通过 `observability` 完成配置,无需再通过额外的 Python 参数开关启用

### Requirement: 运行入口不暴露 pretty_logging bool
系统 MUST 从对外运行入口(`run`/`RunOptions`)移除 `pretty_logging: bool` 这类用于选择实现的参数,并改为:
- 通过 YAML `observability.logging.renderer/preset` 选择内置 logging 实现
- 通过统一组件列表装配自定义 `Observer`/`IExecutionHook`

#### Scenario: 通过 YAML 选择 logging renderer
- **WHEN** 用户在 YAML 中配置 logging renderer/preset
- **THEN** 系统按该配置启用对应 logging 实现

#### Scenario: 通过组件列表追加自定义观测
- **WHEN** 用户在运行入口提供组件列表并包含自定义 observer
- **THEN** 系统应注册该 observer 并按其订阅分发事件

### Requirement: runtime 编译链路保持 batch_size 的 None 语义
by_yaml runtime compiler MUST 将 YAML/RunOptions 的 `batch_size` 编译为 `ExecutionRequest.batch_size: Optional[int]`,并保持 `None` 语义可穿透 execution.
编译链路 MUST NOT 使用 truthy fallback(例如 `a or b`)决定 `batch_size`,以避免吞掉显式 `null`.

当需要决定 effective batch_size 时,系统 MUST 使用显式空值判断:
- 优先使用调用参数中的显式整数(若提供).
- 否则使用 YAML 配置中的 `batch_size`(可为 `None`).
- `None` 必须被视为合法值并保留给 execution 层解释为 no-chunking.

#### Scenario: YAML null 编译为 request None
- **WHEN** YAML 声明 `batch_size: null` 且运行参数未显式传入整数覆盖
- **THEN** compiler 产出的 `ExecutionRequest.batch_size` MUST 为 `None`

#### Scenario: 运行参数整数覆盖 YAML null
- **WHEN** YAML 声明 `batch_size: null` 且运行参数显式传入 `batch_size=256`
- **THEN** compiler 产出的 `ExecutionRequest.batch_size` MUST 为 `256`

### Requirement: YAML retry 编译为 DSL-agnostic 的 execution request
系统 MUST 在 by_yaml runtime 编译期将 YAML 的 retry 配置编译为 DSL-agnostic 的 execution request(例如 `ExecutionRequest`)中的 loader retry policy 字段,并在执行期由 execution 层统一消费.
当未提供任何 retry 配置时,该 request 字段 MUST 保持缺省/disabled,从而不改变现有执行行为.

#### Scenario: YAML retry 缺省时 request 不启用 retry
- **WHEN** YAML 未声明任何 `retry`
- **THEN** 编译产出的 execution request MUST 不启用 loader retry(等价于 disabled)

### Requirement: driver 注入优先于 YAML 编译结果
系统 SHALL 允许调用方在 runtime/driver 层显式注入 loader retry policy(用于统一处理异常与策略),其优先级 MUST 高于 YAML 中的 retry 配置(与 guardrails 的覆盖语义一致).

#### Scenario: driver 覆盖 YAML retry
- **GIVEN** YAML 中声明 `retry.max_attempts=3`
- **WHEN** 调用方显式注入 policy 且 `max_attempts=5`
- **THEN** effective policy MUST 使用 `max_attempts=5`

### Requirement: fields validator 热点必须按规则职责拆分并保持稳定 validator 入口
系统 MUST 允许将 `config_parsing/validators/fields.py` 按规则职责拆分为多个内部子模块,例如字段通用校验、output 字段校验、issue 收集或辅助逻辑,但 `config_parsing.validator` 与既有稳定导入路径 MUST 保持可用且行为等价.

#### Scenario: fields validator 拆分后稳定入口保持
- **WHEN** 维护者拆分 `config_parsing/validators/fields.py`
- **THEN** 调用方通过 `IMPL_ROOT.dsl.by_yaml.config_parsing.validator` 的既有关键类型导入 MUST 继续成功
- **AND** YAML 校验输出与错误语义 MUST 与重构前保持等价

### Requirement: runtime conversion 热点必须按阶段职责拆分并保持编译链路边界
系统 MUST 允许将 `runtime/conversion.py` 按阶段职责拆分为内部协作单元,至少包括 registry/helper、Config→IR 转换、运行请求映射等边界,且不得重新把多阶段职责聚回单一热点实现.

#### Scenario: conversion 拆分后编译链路边界清晰
- **WHEN** 维护者重构 `runtime/conversion.py`
- **THEN** Config→IR 转换、运行请求映射与辅助 registry 逻辑 MUST 具备可独立验证的边界
- **AND** 现有 YAML runtime 入口行为 MUST 与重构前保持一致
