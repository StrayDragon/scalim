## ADDED Requirements

### Requirement: 输出模式对比

output 专题指南文档 MUST 提供三种输出模式的对比表格，包含行为、推荐度、使用场景和配置复杂度。

#### Scenario: 用户查看输出模式对比
- **WHEN** 用户打开 output 专题指南
- **THEN** 文档 MUST 显示包含以下列的对比表格：
  - 模式名称
  - 推荐度（⭐⭐⭐ / ⭐⭐）
  - 行为说明
  - 使用场景
  - 配置复杂度

### Requirement: Detail 输出详细说明

output 专题指南文档 MUST 为 detail 输出模式提供详细说明，标注为 ⭐⭐⭐ 推荐度。

#### Scenario: 用户学习 detail 输出
- **WHEN** 用户阅读 detail 输出章节
- **THEN** 文档 MUST 说明：
  - 行为：输出明细数据
  - fields 配置：字段列表
  - to.book / to.sheet 绑定
  - 适用场景：大部分输出场景
  - 示例代码

### Requirement: Where 过滤详细说明

output 专题指南文档 MUST 为 where 过滤模式提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 where 过滤
- **WHEN** 用户阅读 where 过滤章节
- **THEN** 文档 MUST 说明：
  - 行为：条件过滤分发
  - where 表达式：布尔表达式
  - from 复用：继承字段和容器配置
  - 适用场景：条件分发到不同 sheet
  - 示例代码

### Requirement: Aggregate 输出详细说明

output 专题指南文档 MUST 为 aggregate 输出模式提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 aggregate 输出
- **WHEN** 用户阅读 aggregate 输出章节
- **THEN** 文档 MUST 说明：
  - 行为：聚合汇总输出
  - group_by 配置：分组字段
  - fields 配置：聚合算子
  - guardrails 配置：max_groups, max_distinct
  - 适用场景：汇总统计
  - 示例代码

### Requirement: Aggregate 算子详解

output 专题指南文档 MUST 提供聚合算子的详细说明。

#### Scenario: 用户学习基础算子
- **WHEN** 用户阅读基础算子章节
- **THEN** 文档 MUST 说明：
  - count：计数
  - sum：求和
  - min：最小值
  - max：最大值
  - 适用场景：90% 聚合场景
  - 示例代码

#### Scenario: 用户学习高级算子
- **WHEN** 用户阅读高级算子章节
- **THEN** 文档 MUST 说明：
  - count_distinct：去重计数
  - count_true：真值计数
  - count_true_gte：大于等于阈值计数
  - rank：排序排名
  - 适用场景：特定统计需求
  - 示例代码

### Requirement: Guardrails 配置说明

output 专题指南文档 MUST 说明 guardrails 配置的使用方法。

#### Scenario: 用户学习 guardrails
- **WHEN** 用户阅读 guardrails 章节
- **THEN** 文档 MUST 说明：
  - max_groups：最大分组数
  - max_distinct：最大去重数
  - distinct_on_overflow：溢出策略
  - 适用场景：防止聚合结果过大
  - 推荐配置

### Requirement: 资源绑定说明

output 专题指南文档 MUST 说明资源绑定的使用方法。

#### Scenario: 用户学习资源绑定
- **WHEN** 用户阅读资源绑定章节
- **THEN** 文档 MUST 说明：
  - resources.books/files 复用
  - to.book / to.sheet 绑定
  - 内联资源声明（可选）
  - 示例代码

### Requirement: YAML Merge 复用说明

output 专题指南文档 MUST 说明 YAML merge 复用模式的使用方法。

#### Scenario: 用户学习 YAML merge
- **WHEN** 用户阅读 YAML merge 章节
- **THEN** 文档 MUST 说明：
  - `<<: *ref` 语法
  - 与 from 复用的对比
  - 适用场景
  - 注意事项

### Requirement: From 复用机制说明

output 专题指南文档 MUST 说明 from 复用机制的使用方法。

#### Scenario: 用户学习 from 复用
- **WHEN** 用户阅读 from 复用章节
- **THEN** 文档 MUST 说明：
  - from 的作用：继承字段和容器配置
  - 字段继承：复用字段列表
  - 容器继承：复用 to.book / to.sheet
  - 适用场景
  - 示例代码

### Requirement: 选择决策树

output 专题指南文档 MUST 提供选择决策树，帮助用户根据场景选择合适的输出模式。

#### Scenario: 用户使用决策树选择模式
- **WHEN** 用户需要配置 output
- **THEN** 决策树 MUST 引导用户：
  - 输出明细？→ detail
  - 条件分发？→ where
  - 汇总统计？→ aggregate

### Requirement: 推荐度标注

output 专题指南文档 MUST 为每种输出模式标注推荐度。

#### Scenario: 用户查看推荐度
- **WHEN** 用户浏览 output 专题指南
- **THEN** 每种模式 MUST 显示推荐度：
  - detail → ⭐⭐⭐
  - where → ⭐⭐
  - aggregate → ⭐⭐

### Requirement: 文档维护规范

output-guide.md MUST 遵循项目文档治理规则：
- 不包含 `.gen.` 后缀（手工维护）
- 不使用 `<!-- BEGIN/END AUTOGEN -->` 注入块
- 内容变更不依赖 `just gen-docs` 重新生成

#### Scenario: 文档入口链接
- **WHEN** output-guide.md 创建完成
- **THEN** usage-guide.md MUST 包含指向 output-guide.md 的链接
