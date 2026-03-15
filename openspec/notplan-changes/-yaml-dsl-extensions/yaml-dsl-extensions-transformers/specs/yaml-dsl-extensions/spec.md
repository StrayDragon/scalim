## ADDED Requirements

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

### Requirement: transformers 的执行顺序必须确定性
系统 MUST 以确定性顺序执行 transformers,避免“同一 YAML 在不同入口产生不同结构”的漂移.

约束:
- stage 顺序 MUST 固定为 `raw` → `config` → `ir` → `request`
- 单 stage 内:
  - direct config transformers MUST 先于 bundles transformers 执行
  - 同一来源内 MUST 按 YAML 声明顺序执行

#### Scenario: 多个 transformers 按声明顺序生效
- **GIVEN** `extensions.transform.raw` 声明两个 transformers,第一个写入键 `x: 1`,第二个将其改写为 `x: 2`
- **WHEN** 编译 YAML
- **THEN** validator MUST 看到 `x == 2`

### Requirement: transformer 异常必须包含 `yaml_path/ref/stage` 上下文
系统 MUST 在 transformer 执行失败时提供可行动错误上下文,至少包含:
- `ref`(导致错误的 transformer 引用)
- `stage`(例如 `extensions.transform.raw`)
- 当 `yaml_path` 可得时,错误 MUST 包含 `yaml_path`

#### Scenario: transformer 抛错时包含 ref 与 stage
- **GIVEN** 某 transformer 在执行时抛出异常
- **WHEN** 系统执行该 transformer
- **THEN** 错误 MUST 包含该 transformer 的 ref 与其 stage
