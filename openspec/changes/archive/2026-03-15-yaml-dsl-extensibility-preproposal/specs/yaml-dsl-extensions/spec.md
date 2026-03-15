## ADDED Requirements

### Requirement: YAML DSL 提供顶层 `extensions` 扩展入口
系统 SHALL 在 YAML DSL 顶层提供可选对象 `extensions`,用于在“可信 YAML(trusted)”场景下声明要启用的对外扩展.

#### Scenario: 未声明 extensions 时行为不变
- **GIVEN** 一份不包含 `extensions` 的 YAML DSL
- **WHEN** 调用 `scalim.dsl.by_yaml.run/compile`
- **THEN** 系统行为 MUST 与当前版本一致(不额外导入扩展、不装配额外组件、不改变 compute/outputs 语义)

#### Scenario: extensions.enabled=false 禁用扩展
- **GIVEN** YAML 顶层包含 `extensions` 且 `enabled: false`
- **WHEN** 调用 `scalim.dsl.by_yaml.run/compile`
- **THEN** 系统 MUST 不加载/执行任何扩展声明,并保持行为与“未声明 extensions”一致

### Requirement: `extensions.api` 作为扩展契约版本号
系统 MUST 支持 `extensions.api`(整数)作为扩展契约版本号,用于控制扩展语义的演进与对拍.

约束:
- 当 `extensions.api` 缺省时,系统 MUST 将其视为 `1`
- 当 `extensions.api` 为未知值时,系统 MUST fail-fast 并给出可行动错误(包含期望版本集合与当前值)

#### Scenario: 缺省 api 视为 1
- **GIVEN** YAML 顶层包含 `extensions: {enabled: true}` 且未声明 `api`
- **WHEN** 启用扩展解析并编译该 YAML
- **THEN** 系统 MUST 将 `extensions.api` 视为 `1`

#### Scenario: 未知 api fail-fast
- **GIVEN** YAML `extensions.api: 999`
- **WHEN** 启用扩展解析并编译该 YAML
- **THEN** 系统 MUST fail-fast 并提示升级/降级或禁用 extensions

### Requirement: 扩展引用必须通过 allowlist resolver 显式解析
系统 MUST 复用现有 `SecurePythonReferenceResolver` 解析 YAML 中的扩展引用(函数/类/工厂),并继续受 `allowed_modules/allowed_functions` 与相对引用归一化约束.

#### Scenario: 扩展引用不在 allowlist 时失败
- **GIVEN** YAML `extensions` 中声明某扩展引用 `ref: myapp.ext:foo`
- **AND** 运行入口未将 `myapp` 纳入 `allowed_modules/allowed_functions`
- **WHEN** 编译该 YAML
- **THEN** 系统 MUST 在编译期 fail-fast 并给出可行动错误(至少包含扩展 ref 与“allowlist 不包含”的原因)

### Requirement: 支持 extension bundles(工厂返回扩展贡献集合)
系统 SHALL 支持在 `extensions.bundles` 中声明若干 “bundle factory”,并在编译期调用以获得扩展贡献集合(例如 compute 函数、components、transformers、format registry 等).

#### Scenario: bundle factory 返回 compute 函数与 components
- **GIVEN** `extensions.bundles` 声明一个 bundle factory
- **WHEN** 该 factory 返回 compute 函数映射与 components 列表
- **THEN** 系统 MUST 合并这些贡献并在本次编译/执行中生效

### Requirement: 扩展可从 YAML 装配 components(Observer/Hook)
系统 SHALL 允许从 YAML 的 `extensions` 中装配额外 components,并复用 `split_components` 对类型进行显式校验:
- `Observer` 走 observer 装配路径
- `IExecutionHook` 走 hook 装配路径
- 其它对象 MUST 抛出 `TypeError` 并包含 index/type 与期望类型

#### Scenario: 非法 component 尽早失败
- **GIVEN** `extensions` 声明的 components 列表包含非 `Observer`/非 `IExecutionHook` 的对象
- **WHEN** 编译/装配该 YAML
- **THEN** 系统 MUST 在装配阶段抛出 `TypeError`(而不是运行到中后期才失败)

### Requirement: 扩展可注册 compute/where 的额外函数名与实现
系统 SHALL 允许扩展为安全表达式引擎(`SecureComputeEngine`)注册额外函数(函数名 + Python 实现),使以下表达式可使用这些函数:
- 派生字段 `compute`
- outputs 的 `where`(若使用 compute 表达式形态)

#### Scenario: compute 表达式可使用扩展函数
- **GIVEN** 扩展注册了函数名 `safe_div`
- **AND** YAML 派生字段包含表达式 `compute: "safe_div(a, b)"`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 允许该表达式通过校验与编译,并在执行时使用扩展提供的实现完成求值

### Requirement: 同时支持 Direct config + BUNDLE,并合并为同一扩展视图
系统 SHALL 允许用户在同一份 YAML 中同时使用:
- `extensions.compute/components/outputs/aggregates/transform` 等 direct config
- `extensions.bundles` 声明的 bundle factories

系统 MUST 将它们合并为同一组“扩展贡献”(registries/components/transformers/analyzers)并在本次编译/执行中一致生效.

#### Scenario: direct config 与 bundle 同时生效
- **GIVEN** YAML 在 `extensions.compute.functions` 中声明函数 `safe_div`
- **AND** YAML 同时在 `extensions.bundles` 中声明一个 bundle,该 bundle 额外注册函数 `safe_mul`
- **WHEN** 编译并执行该 YAML
- **THEN** `compute` 表达式 MUST 同时可使用 `safe_div` 与 `safe_mul`

### Requirement: 支持 ANALYZE 扩展点(只读分析器)
系统 SHALL 支持 `extensions.analyze` 声明 analyzers,analyzer 通过 Python 引用加载并在显式启用扩展的情况下执行.

约束:
- analyzer MUST 为只读(不得修改 raw/config/IR/request 的最终语义);其输出仅用于诊断/建议/元信息
- analyzer 失败 MUST 产生可行动错误(包含 analyzer ref 与执行阶段),并允许配置 fail-fast 或降级为 warning

#### Scenario: analyzer 产出告警
- **GIVEN** YAML `extensions.analyze` 声明了一个 analyzer
- **WHEN** 用户在“启用扩展分析”的模式下运行编译/校验
- **THEN** 系统 MUST 将 analyzer 产出的 warning/errors 合并到校验结果中(可被 CLI/CI 消费)

### Requirement: 输出格式 registry 可扩展,并可被 YAML outputs 使用
系统 SHALL 允许扩展注册 `output format id → factory` 的映射,并允许 YAML `outputs[*].container.type` 使用自定义 format id.

约束:
- 内置 `workbook/csv` MUST 保持兼容
- 当 `container.type` 为非内置值时,系统 MUST 通过 registry 解析并创建输出端
- `container.options`(若存在) MUST 作为扩展配置传入 factory

#### Scenario: 自定义 format id 可用于 outputs
- **GIVEN** 扩展注册了 format id `parquet`
- **AND** YAML `outputs[0].container.type: parquet`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 通过 registry 创建该输出目标的 sink,并写出结果(或在 factory 不满足约束时给出可行动错误)

### Requirement: 自定义 aggregate kind/ref 可编译为派生聚合
系统 SHALL 允许 YAML `outputs[*].aggregate` 使用自定义 kind/ref 形态,并通过扩展工厂编译为派生聚合输出.

约束:
- 自定义 aggregate 工厂 MUST 返回可执行的派生聚合描述(至少包含 `IDerivedAggregationSpec` 与输出字段列表)
- 系统 MUST 使用该派生聚合的 `required_fields()` 将依赖字段注入到 required_demand_fields,以保证 planner/executor 可得到完整依赖闭包

#### Scenario: 自定义 aggregate 注入 required fields
- **GIVEN** YAML `outputs[0].aggregate` 使用自定义 kind 且其 `required_fields()` 返回字段 `a/b`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 将 `a/b` 纳入本次运行的 required 字段集合,确保执行期不会因缺失依赖字段而失败

### Requirement: 支持 transformers(编译期可变换器),并按阶段执行
系统 SHALL 支持扩展提供 transformers,并允许按阶段挂载:
- raw transformers: 在 imports 展开后、核心 validator 前执行
- config transformers: 在 DemandConfig 解析后执行
- ir transformers: 在 DemandIr 构造后执行
- request transformers: 在 ExecutionRequest 装配后执行

#### Scenario: raw transformer 在 validator 前生效
- **GIVEN** 扩展声明一个 raw transformer,将 raw dict 中的某个宏键展开为标准字段
- **WHEN** 编译 YAML
- **THEN** validator MUST 看到 transformer 后的 raw 配置(使宏展开对校验与后续编译一致生效)

### Requirement: compute 依赖推导 MUST 忽略函数名
系统 MUST 在推导 compute/where 的字段依赖时忽略函数名(即 `Call.func`),避免扩展函数名被误判为字段依赖.

#### Scenario: safe_div 不应成为依赖字段
- **GIVEN** 扩展注册了函数名 `safe_div`
- **AND** 表达式为 `safe_div(a, b)`
- **WHEN** 系统推导该表达式的字段依赖
- **THEN** 依赖列表 MUST 仅包含 `a` 与 `b`(不包含 `safe_div`)

### Requirement: 冲突策略确定性且可配置
系统 MUST 为扩展贡献的合并提供确定性顺序与冲突策略,至少覆盖:
- compute functions 同名冲突
- output formats 同名冲突
- aggregate kinds 同名冲突

#### Scenario: 冲突策略为 error 时 fail-fast
- **GIVEN** 两个 bundles 注册了同名 compute function `safe_div`
- **AND** 冲突策略配置为 `error`
- **WHEN** 编译该 YAML
- **THEN** 系统 MUST fail-fast 并给出可行动错误(包含冲突键名与来源 ref 列表)

### Requirement: 自定义 aggregate 的 required_fields 必须进入 required 字段闭包
系统 MUST 确保自定义 aggregate 的 `derived.required_fields()` 在字段裁剪/IR 构造前即可生效,避免 composed outputs 运行时缺字段.

#### Scenario: required_fields 注入到 required 闭包
- **GIVEN** YAML outputs 使用自定义 aggregate kind/ref
- **AND** 该 aggregate 的 `derived.required_fields()` 返回字段 `a/b`
- **WHEN** 系统编译该 YAML 并构建执行计划
- **THEN** 执行计划 MUST 包含 `a/b` 作为 required 字段(不会因字段裁剪缺失而失败)

### Requirement: output format factory MUST 可接收 `container.options`
系统 MUST 将 YAML `outputs[*].container.options`(若存在)传递给对应的 output format factory,以支持扩展格式的自定义行为.

#### Scenario: options 透传给 factory
- **GIVEN** YAML `outputs[0].container.type: parquet`
- **AND** YAML `outputs[0].container.options: {compression: zstd}`
- **WHEN** 系统通过 registry 创建该输出 sink
- **THEN** factory MUST 能读取到 `options.compression == "zstd"`
