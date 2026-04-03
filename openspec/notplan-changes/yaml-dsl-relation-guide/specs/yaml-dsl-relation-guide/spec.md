## ADDED Requirements

### Requirement: 三种引用方式对比

relation 专题指南文档 MUST 提供三种引用方式的对比表格，包含语法、推荐度、使用场景和限制。

#### Scenario: 用户查看引用方式对比
- **WHEN** 用户打开 relation 专题指南
- **THEN** 文档 MUST 显示包含以下列的对比表格：
  - 引用方式
  - 推荐度（⭐⭐⭐ / ⭐⭐ / ⭐）
  - 语法示例
  - 使用场景
  - 限制说明

### Requirement: String Ref 详细说明

relation 专题指南文档 MUST 为 string ref 引用方式提供详细说明，标注为 ⭐⭐⭐ 推荐度。

#### Scenario: 用户学习 string ref 语法
- **WHEN** 用户阅读 string ref 章节
- **THEN** 文档 MUST 说明：
  - 语法：`relation: <relation_id>`
  - 优势：LSP 友好、支持跨文件引用
  - 适用场景：90% 的关联场景
  - 示例代码

#### Scenario: 用户了解 string ref 的优势
- **WHEN** 用户考虑选择 string ref
- **THEN** 文档 MUST 说明其优势：
  - LSP 可以自动补全 relation_id
  - 支持跨文件引用（imports）
  - 便于重构和重命名

### Requirement: YAML Alias 详细说明

relation 专题指南文档 MUST 为 YAML alias 引用方式提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 YAML alias 语法
- **WHEN** 用户阅读 YAML alias 章节
- **THEN** 文档 MUST 说明：
  - 语法：`relation: *<anchor_name>`
  - 适用场景：_templates 复用
  - 限制：仅限文件内复用
  - 示例代码

#### Scenario: 用户了解 YAML alias 的使用场景
- **WHEN** 用户考虑选择 YAML alias
- **THEN** 文档 MUST 说明：
  - 主要用于 _templates 复用场景
  - 与 string ref 的区别
  - 不推荐用于普通关联定义

### Requirement: Inline Steps 详细说明

relation 专题指南文档 MUST 为 inline steps 引用方式提供详细说明，标注为 ⭐ 推荐度。

#### Scenario: 用户学习 inline steps 语法
- **WHEN** 用户阅读 inline steps 章节
- **THEN** 文档 MUST 说明：
  - 语法：`relation: {steps: [...]}`
  - 适用场景：一次性关联
  - 限制：不可复用、LSP 支持有限
  - 示例代码

#### Scenario: 用户了解 inline steps 的限制
- **WHEN** 用户考虑选择 inline steps
- **THEN** 文档 MUST 说明其限制：
  - 不可复用
  - LSP 自动补全支持有限
  - 推荐优先使用 named relation

### Requirement: 性能考虑说明

relation 专题指南文档 MUST 包含性能考虑章节，说明 named relations 和 inline relations 的性能差异。

#### Scenario: 用户了解性能考虑
- **WHEN** 用户阅读性能考虑章节
- **THEN** 文档 MUST 说明：
  - named relations 的性能优势（可复用编译结果）
  - inline relations 的性能特征（每次内联编译）
  - 复用机制的性能影响

### Requirement: 选择决策树

relation 专题指南文档 MUST 提供选择决策树，帮助用户根据场景选择合适的引用方式。

#### Scenario: 用户使用决策树选择引用方式
- **WHEN** 用户需要配置 relation
- **THEN** 决策树 MUST 引导用户：
  - 关联是否需要复用？是 → 使用 string ref
  - 是否在 _templates 中复用？是 → 使用 YAML alias
  - 是否为一次性关联？是 → 可使用 inline steps

### Requirement: 推荐度标注

relation 专题指南文档 MUST 为每种引用方式标注三级推荐度。

#### Scenario: 用户查看推荐度
- **WHEN** 用户浏览 relation 专题指南
- **THEN** 每种引用方式 MUST 显示推荐度：
  - string ref → ⭐⭐⭐
  - YAML alias → ⭐⭐
  - inline steps → ⭐

### Requirement: 文档维护规范

relation-guide.md MUST 遵循项目文档治理规则：
- 不包含 `.gen.` 后缀（手工维护）
- 不使用 `<!-- BEGIN/END AUTOGEN -->` 注入块
- 内容变更不依赖 `just gen-docs` 重新生成

#### Scenario: 文档内容更新
- **WHEN** relation 行为发生变化
- **THEN** 维护者 MUST 手工更新 relation-guide.md 中的相关说明
- **AND** 保持与 schema hover 文档的一致性

#### Scenario: 文档入口链接
- **WHEN** relation-guide.md 创建完成
- **THEN** usage-guide.md MUST 包含指向 relation-guide.md 的链接
