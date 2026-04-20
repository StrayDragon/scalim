# governance-mainline-principles Specification

## Purpose
定义 YAML DSL 的上位主线原则与设计护栏，用于约束后续变更的方向与评审口径：单主线原地演进、authoring/runtime policy 分离、KV-first、以及 workflow 小而声明式（拒绝 imports expansion）。

## Related Concepts
- YAML DSL 主线演进策略
- Authoring surface 与 runtime policy 分离
- KV-first 设计模式
- Workflow orchestration 边界

## Requirements
### Requirement: YAML DSL mainline MUST evolve as a single in-place line
YAML DSL 主线演进 MUST 采用单主线原地升级模型:

- 系统 MUST NOT 引入 `dsl_version`
- 系统 MUST NOT 通过 CLI、schema 路径或 modeline 选择并行 DSL 版本
- 系统 MUST NOT 维护并行 parser、validator 或 schema 产物来长期承载旧写法

#### Scenario: future cleanup does not add a parallel parser
- **WHEN** 某个后续变更需要清理旧 YAML 写法
- **THEN** 方案 MUST 选择原地迁移、lint 或升级提示
- **AND** MUST NOT 新增并行版本解析链路

### Requirement: Mainline YAML MUST keep authoring separate from runtime policy
主线 YAML MUST 聚焦 authoring surface,而运行环境、性能预算、集成策略类能力 MUST 收口到 Python / CLI runtime entrypoints:

- authoring surface MUST 以 `sources`、`fields`、`relations`、`outputs` 与少量资源声明为中心
- environment-sensitive knobs MUST NOT 作为主线 YAML 的优先承载面

#### Scenario: environment-sensitive control is routed to runtime entrypoints
- **WHEN** 某个字段的启停明显取决于环境、性能预算或运行入口集成
- **THEN** 该能力 MUST 优先设计到 Python / CLI runtime entrypoints
- **AND** MUST NOT 被继续扩大为主线 YAML authoring surface

### Requirement: Mainline YAML structures MUST be KV-first unless order is semantic
凡是需要稳定标识、引用或复用的 YAML 结构 MUST 优先采用 mapping / KV 形式;只有顺序本身具有业务语义时才使用 list。

#### Scenario: reusable keyed nodes use mappings
- **WHEN** 系统新增一个需要稳定 ID 与跨节点引用的 YAML 结构
- **THEN** 该结构 MUST 优先采用 mapping / KV 形式
- **AND** 只有在顺序不可替代时才允许采用 list

### Requirement: Workflow MUST remain a small declarative orchestration surface
workflow MUST 保持“小而声明式”的 orchestration DSL:

- workflow MUST 聚焦 runs、依赖关系、上下文传递与少量稳定的 orchestration knobs
- workflow MUST NOT 扩张为 imports fragment composition surface

#### Scenario: workflow rejects imports expansion as a design direction
- **WHEN** 有提案希望在 workflow 中新增 imports expansion
- **THEN** 该方向 MUST 被视为偏离 workflow 主线职责
- **AND** 应改为通过 demand authoring 复用或 runtime assembly 解决
