## ADDED Requirements

### Requirement: Provide a single canonical YAML DSL syntax
系统 MUST 定义并交付一个“唯一 canonical”的 YAML DSL 语法,并将其作为仓库内所有示例/fixtures/docs/skill/editor 的唯一写法。
系统 MUST NOT 引入 `v1/v2/v3` 等版本预设标签;旧写法通过升级链路一次性迁移,迁移后仓库只保留最新语义。

#### Scenario: 仓库示例保持最新语义
- **WHEN** 维护者合入新的 YAML DSL 语法实现
- **THEN** 仓库内 `tests/fixtures`、`notebooks/marimo/**/by_yaml_dsl/*.yaml`、`artifacts/skills/**/example*.yaml` MUST 仅包含最新写法

### Requirement: Candidate plans are reviewable with MVP examples
系统 MUST 提供不少于 5 套候选语法方案,每套方案 MUST 包含可 review 的完整 MVP 示例 YAML,用于对比“同一业务配置在不同语法下的可读性与一致性”。

#### Scenario: 每套方案都有可读 MVP
- **WHEN** 维护者提交候选方案提案
- **THEN** 每个 `mvp/plan-*` MUST 至少包含 `plan.md` 与 `mvp.yaml`

### Requirement: No required YAML anchors/alias for correctness
新的 canonical YAML DSL 语法 MUST NOT 依赖 YAML anchors/alias 的“对象身份”才能正确解析;anchors/alias 只能作为可选复用手段。

#### Scenario: 没有 anchors 的配置仍可表达输出字段
- **WHEN** 用户不使用 anchors/alias 编写配置
- **THEN** 系统仍能解析 output/select 字段顺序与字段覆写,且不依赖对象身份匹配

### Requirement: References use explicit identifiers
新的 canonical YAML DSL 语法 MUST 提供统一的显式引用语义用于复用与链接(例如 relation/field/source 的引用),并避免“只能内联 steps 或只能 alias”的写法。

#### Scenario: relation 可以通过显式 ref 引用
- **WHEN** 用户在字段定义中引用 relation
- **THEN** 该引用 MUST 支持稳定的显式 ref 语义(例如 `ref: orders_to_customers` 或等价形式),并可被 JSON Schema 与 validator 解释

### Requirement: Capability parity with current YAML DSL
新的 canonical YAML DSL 语法 MUST 覆盖当前 DSL 的核心能力边界(表达方式允许变化,语义能力不得缩水),至少包含:
- main source + multiple sources
- relation steps(单级/多级/复合键) + lookup_cast
- source field extract/value_cast + derived compute/call_by
- params 模板(运行期变量与 keys/rows 注入)
- cache_mode(preload_forever) + normalize
- output(字段顺序/覆写/streaming/format)
- guardrails + observability + retry

#### Scenario: canonical example 覆盖核心能力
- **WHEN** 维护者提供 canonical full example
- **THEN** 示例 MUST 至少包含 1 个 join、1 个 derived、1 个 params 注入、1 个 output 配置与 1 个 observability 子配置

### Requirement: Schema + semantic validation remain first-class
系统 MUST 为新的 canonical YAML DSL 语法提供:
- JSON Schema(用于 LSP/editor 与 schema-only 校验)
- 语义 validator(用于安全引用、unknown fields 诊断与复杂约束)

#### Scenario: schema-only 与 full validate 可用
- **WHEN** 用户执行 schema-only 校验
- **THEN** 系统使用 JSON Schema 验证结构与类型
- **WHEN** 用户执行 full validate
- **THEN** 系统额外执行语义 validator 并给出可操作诊断

### Requirement: One-step migration and upgrade guide
系统 MUST 提供一步到位的升级链路,将旧写法直接迁移到最新语义,并提供可索引的升级指南文档。

#### Scenario: 升级文档可被 skill 索引
- **WHEN** 维护者完成一次 breaking 语法变更并归档 change
- **THEN** `artifacts/skills/scalim-yaml-dsl/references/upgrades/` MUST 增加升级指南并可被 skill references 自动索引
