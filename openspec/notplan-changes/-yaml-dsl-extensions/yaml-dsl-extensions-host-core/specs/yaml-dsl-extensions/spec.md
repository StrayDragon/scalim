## ADDED Requirements

### Requirement: YAML DSL 提供顶层 `extensions` 扩展入口
系统 SHALL 在 YAML DSL 顶层提供可选对象 `extensions`,用于在“可信 YAML(trusted)”场景下声明要启用的对外扩展.

约束:
- 当 `extensions` 缺省时,系统行为 MUST 与当前版本一致
- 当 `extensions.enabled=false` 时,系统 MUST 跳过所有 extensions 的解析/导入/执行,并保持行为与“未声明 extensions”一致
- 当 `extensions` 存在但未声明 `enabled` 时,系统 MUST 将其视为 `true`

#### Scenario: 未声明 extensions 时行为不变
- **GIVEN** 一份不包含 `extensions` 的 YAML DSL
- **WHEN** 调用 `scalim.dsl.by_yaml.run/compile`
- **THEN** 系统行为 MUST 与当前版本一致(不额外导入扩展、不装配额外组件、不改变 compute/outputs 语义)

#### Scenario: extensions.enabled=false 禁用扩展
- **GIVEN** YAML 顶层包含 `extensions` 且 `enabled: false`
- **WHEN** 调用 `scalim.dsl.by_yaml.run/compile`
- **THEN** 系统 MUST 不加载/执行任何扩展声明,并保持行为与“未声明 extensions”一致

#### Scenario: enabled 缺省视为 true
- **GIVEN** YAML 顶层包含 `extensions` 且未声明 `enabled`
- **WHEN** 调用 `scalim.dsl.by_yaml.run/compile`
- **THEN** 系统 MUST 将该 `extensions` 视为启用状态(等价于 `enabled: true`)

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

#### Scenario: 相对引用在缺失 yaml_path 时失败
- **GIVEN** YAML `extensions` 中声明相对引用 `ref: .ext:foo`
- **AND** 编译入口无法提供 `yaml_path`(例如 string entrypoint)
- **WHEN** 系统尝试解析该扩展引用
- **THEN** 系统 MUST fail-fast 并提示相对引用需要 `yaml_path` 或必须改写为绝对引用

### Requirement: `ExtensionHost` 作为编译期唯一扩展产物(SSOT)
系统 MUST 在编译期解析并合并 direct config 与 bundles,产出可复用的 `ExtensionHost`,供 validator/parser/compiler/executor/CLI 共享,避免扩展视图漂移.

约束:
- 构建 `ExtensionHost` 的过程 MUST 为确定性(同一 YAML + 同一 allowlist → 相同贡献视图与 summary)
- direct config 与 bundles 的合并顺序 MUST 确定(见后续 requirement)

#### Scenario: ExtensionHost.summary 可用于对拍与诊断
- **GIVEN** YAML 启用 extensions 并声明 bundles/direct config
- **WHEN** 系统完成编译
- **THEN** 系统 MUST 生成 `ExtensionHost.summary`
- **AND** summary MUST 包含最终启用的 bundles/registries/components 列表(含来源 ref),用于对拍与排障

### Requirement: 支持 extension bundles(工厂返回扩展贡献集合)
系统 SHALL 支持在 `extensions.bundles` 中声明若干 “bundle factory”,并在编译期调用以获得扩展贡献集合(例如 compute 函数、components、transformers、format registry 等).

#### Scenario: bundle factory 的贡献进入 ExtensionHost 视图
- **GIVEN** `extensions.bundles` 声明一个 bundle factory
- **WHEN** 该 factory 返回 compute 函数映射与 components 列表
- **THEN** 系统 MUST 将这些贡献合并进本次编译产物 `ExtensionHost`(至少在 `summary` 中可对拍)

### Requirement: 同时支持 Direct config + BUNDLE,并合并为同一扩展视图
系统 SHALL 允许用户在同一份 YAML 中同时使用:
- `extensions.compute/components/outputs/aggregates/transform` 等 direct config
- `extensions.bundles` 声明的 bundle factories

系统 MUST 将它们合并为同一组“扩展贡献”(registries/components/transformers/analyzers)并在本次编译/执行中一致生效.

#### Scenario: direct config 与 bundle 的贡献同时进入 ExtensionHost
- **GIVEN** YAML 在 `extensions.compute.functions` 中声明函数 `safe_div`
- **AND** YAML 同时在 `extensions.bundles` 中声明一个 bundle,该 bundle 额外注册函数 `safe_mul`
- **WHEN** 编译该 YAML 并构建 `ExtensionHost`
- **THEN** `ExtensionHost` 中的 compute functions registry MUST 同时包含 `safe_div` 与 `safe_mul`

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

#### Scenario: 冲突策略为 last_wins 时后者覆盖
- **GIVEN** 两个 bundles 注册了同名 compute function `safe_div`
- **AND** 冲突策略配置为 `last_wins`
- **WHEN** 编译该 YAML
- **THEN** 系统 MUST 以确定性顺序选择后者贡献作为最终值

### Requirement: 扩展失败时错误必须包含 `yaml_path/ref/stage` 上下文
系统 MUST 在扩展解析/实例化/合并失败时提供可行动错误上下文,至少包含:
- `yaml_path`(若可得)
- `ref`(导致错误的扩展引用,或其上游 bundle ref)
- `stage`(稳定可 grep 的阶段名,例如 `extensions.resolve_ref`/`extensions.call_bundle`/`extensions.merge`)

#### Scenario: 解析扩展引用失败时包含上下文
- **GIVEN** YAML `extensions.bundles[0].ref` 为非法引用
- **WHEN** 系统解析该引用
- **THEN** 错误 MUST 包含该 ref 与 `extensions.resolve_ref` stage
- **AND** 当 `yaml_path` 可得时,错误 MUST 包含 `yaml_path`

### Requirement: 扩展可从 YAML 装配 components(Observer/Hook)
系统 SHALL 允许从 YAML 的 `extensions` 中装配额外 components,并复用 `split_components` 对类型进行显式校验:
- `Observer` 走 observer 装配路径
- `IExecutionHook` 走 hook 装配路径
- 其它对象 MUST 抛出 `TypeError` 并包含 index/type 与期望类型

#### Scenario: 非法 component 尽早失败
- **GIVEN** `extensions` 声明的 components 列表包含非 `Observer`/非 `IExecutionHook` 的对象
- **WHEN** 编译/装配该 YAML
- **THEN** 系统 MUST 在装配阶段抛出 `TypeError`(而不是运行到中后期才失败)
