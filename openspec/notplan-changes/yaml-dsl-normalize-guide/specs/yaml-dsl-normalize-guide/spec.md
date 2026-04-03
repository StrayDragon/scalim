## ADDED Requirements

### Requirement: 四种预置类型对比

normalize 专题指南文档 MUST 提供四种预置类型的对比表格，包含行为、推荐度、使用场景和复杂度。

#### Scenario: 用户查看类型对比
- **WHEN** 用户打开 normalize 专题指南
- **THEN** 文档 MUST 显示包含以下列的对比表格：
  - 类型名称
  - 推荐度（⭐⭐⭐ / ⭐⭐ / ⭐）
  - 行为说明
  - 使用场景
  - 复杂度

### Requirement: Index_By_Key 详细说明

normalize 专题指南文档 MUST 为 index_by_key 类型提供详细说明，标注为 ⭐⭐⭐ 推荐度。

#### Scenario: 用户学习 index_by_key
- **WHEN** 用户阅读 index_by_key 章节
- **THEN** 文档 MUST 说明：
  - 行为：将 list[row] 归一化为 key -> row 映射
  - on_conflict 策略：error / first / last
  - key_field 配置：可省略，默认取 sources.<id>.key
  - 适用场景：最常见的索引建立
  - 示例代码

### Requirement: Take_First 详细说明

normalize 专题指南文档 MUST 为 take_first 类型提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 take_first
- **WHEN** 用户阅读 take_first 章节
- **THEN** 文档 MUST 说明：
  - 行为：将 mapping[key -> list[row]] 归一化为 mapping[key -> row]
  - on_empty 策略：miss / null / error
  - 适用场景：一对多转一对一
  - 示例代码

### Requirement: Project_Fields 详细说明

normalize 专题指南文档 MUST 为 project_fields 类型提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 project_fields
- **WHEN** 用户阅读 project_fields 章节
- **THEN** 文档 MUST 说明：
  - 行为：对 mapping[key -> row] 的 row value 做投影/重命名
  - on_missing 策略：error / miss / null
  - fields 配置：投影规则
  - from_key 注入：将 lookup key 注入字段
  - 适用场景：字段选择和重命名
  - 示例代码

### Requirement: Map_Values 详细说明

normalize 专题指南文档 MUST 为 map_values 类型提供详细说明，标注为 ⭐ 推荐度。

#### Scenario: 用户学习 map_values
- **WHEN** 用户阅读 map_values 章节
- **THEN** 文档 MUST 说明：
  - 行为：对 mapping 的 values 批量应用 normalize steps
  - steps 链式调用
  - call_by 扩展点
  - 适用场景：复杂转换场景
  - 示例代码

### Requirement: 链式调用说明

normalize 专题指南文档 MUST 说明 steps 链式调用的使用方法。

#### Scenario: 用户学习链式调用
- **WHEN** 用户阅读链式调用章节
- **THEN** 文档 MUST 说明：
  - steps 数组的使用
  - 按顺序应用转换
  - 常见组合模式

#### Scenario: 用户查看常见组合模式
- **WHEN** 用户寻找常见组合
- **THEN** 文档 MUST 提供：
  - take_first + project_fields 组合示例
  - 其他实用组合

### Requirement: Call_By 扩展点说明

normalize 专题指南文档 MUST 说明 call_by 扩展点的使用方法。

#### Scenario: 用户学习 call_by
- **WHEN** 用户阅读 call_by 章节
- **THEN** 文档 MUST 说明：
  - call_by 的作用：受控扩展点
  - 签名要求：Mapping -> Mapping
  - allowlist 约束

### Requirement: 选择决策树

normalize 专题指南文档 MUST 提供选择决策树，帮助用户根据场景选择合适的类型。

#### Scenario: 用户使用决策树选择类型
- **WHEN** 用户需要配置 normalize
- **THEN** 决策树 MUST 引导用户：
  - 建立索引？→ index_by_key
  - 一对多转一对一？→ take_first
  - 字段投影/重命名？→ project_fields
  - 复杂链式转换？→ map_values + steps

### Requirement: 推荐度标注

normalize 专题指南文档 MUST 为每种类型标注三级推荐度。

#### Scenario: 用户查看推荐度
- **WHEN** 用户浏览 normalize 专题指南
- **THEN** 每种类型 MUST 显示推荐度：
  - index_by_key → ⭐⭐⭐
  - take_first → ⭐⭐
  - project_fields → ⭐⭐
  - map_values + steps → ⭐

### Requirement: 文档维护规范

normalize-guide.md MUST 遵循项目文档治理规则：
- 不包含 `.gen.` 后缀（手工维护）
- 不使用 `<!-- BEGIN/END AUTOGEN -->` 注入块
- 内容变更不依赖 `just gen-docs` 重新生成

#### Scenario: 文档入口链接
- **WHEN** normalize-guide.md 创建完成
- **THEN** usage-guide.md MUST 包含指向 normalize-guide.md 的链接
