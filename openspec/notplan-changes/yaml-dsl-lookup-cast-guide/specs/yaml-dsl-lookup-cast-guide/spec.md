## ADDED Requirements

### Requirement: 四种模式对比

lookup_cast 专题指南文档 MUST 提供四种模式的对比表格，包含行为、推荐度、使用场景和注意事项。

#### Scenario: 用户查看模式对比
- **WHEN** 用户打开 lookup_cast 专题指南
- **THEN** 文档 MUST 显示包含以下列的对比表格：
  - 模式名称
  - 推荐度（⭐⭐⭐ / ⭐⭐ / ⭐）
  - 行为说明
  - 使用场景
  - 注意事项

### Requirement: Auto 模式详细说明

lookup_cast 专题指南文档 MUST 为 auto 模式提供详细说明，标注为 ⭐⭐⭐ 推荐度。

#### Scenario: 用户学习 auto 模式
- **WHEN** 用户阅读 auto 模式章节
- **THEN** 文档 MUST 说明：
  - 行为：自动归一化
  - 默认选项：可省略不写
  - float key 拒绝策略
  - 示例代码

#### Scenario: 用户了解 auto 的 float 拒绝策略
- **WHEN** 用户使用 auto 模式
- **THEN** 文档 MUST 说明：
  - auto 会拒绝 float lookup key（避免歧义）
  - 若上游返回 float，请使用 int/str 显式转换

### Requirement: Int / Str 模式详细说明

lookup_cast 专题指南文档 MUST 为 int 和 str 模式提供详细说明，标注为 ⭐⭐ 推荐度。

#### Scenario: 用户学习 int/str 模式
- **WHEN** 用户阅读 int/str 模式章节
- **THEN** 文档 MUST 说明：
  - int 模式：转为 int
  - str 模式：转为 str
  - 适用场景：上游类型不一致
  - 示例代码

### Requirement: Sep_First 模式详细说明

lookup_cast 专题指南文档 MUST 为 sep_first 模式提供详细说明，标注为 ⭐ 推荐度。

#### Scenario: 用户学习 sep_first 模式
- **WHEN** 用户阅读 sep_first 模式章节
- **THEN** 文档 MUST 说明：
  - 行为：按 sep 截取首段后再归一化
  - 适用场景：处理 "1,2,3" 格式的多值 key
  - sep 参数：默认 ","
  - 示例代码

### Requirement: Sep_First 性能警告

lookup_cast 专题指南文档 MUST 为 sep_first 模式提供性能警告，说明 N+1 查询风险。

#### Scenario: 用户了解 sep_first 性能风险
- **WHEN** 用户考虑使用 sep_first
- **THEN** 文档 MUST 警告：
  - 可能导致 N+1 查询问题
  - 每个不同的 key 值都会触发一次 lookup
  - 建议在 loader 中预处理

#### Scenario: 用户查看 sep_first 替代方案
- **WHEN** 用户寻找 sep_first 的替代方案
- **THEN** 文档 MUST 提供：
  - loader 预处理示例
  - 将多值 key 展开为多行的建议

### Requirement: 配置位置说明

lookup_cast 专题指南文档 MUST 说明 lookup_cast 的两种配置位置：source 级别和 step 级别。

#### Scenario: 用户了解配置位置
- **WHEN** 用户阅读配置位置章节
- **THEN** 文档 MUST 说明：
  - source 级别：影响整个 source 的 lookup
  - step 级别：仅影响当前 step 的 lookup
  - 推荐优先使用 source 级别配置

### Requirement: 选择决策树

lookup_cast 专题指南文档 MUST 提供选择决策树，帮助用户根据场景选择合适的模式。

#### Scenario: 用户使用决策树选择模式
- **WHEN** 用户需要配置 lookup_cast
- **THEN** 决策树 MUST 引导用户：
  - 大部分场景 → auto（可省略）
  - 上游类型为 float → int/str
  - 处理 CSV 多值 key → sep_first（注意性能）

### Requirement: 推荐度标注

lookup_cast 专题指南文档 MUST 为每种模式标注三级推荐度。

#### Scenario: 用户查看推荐度
- **WHEN** 用户浏览 lookup_cast 专题指南
- **THEN** 每种模式 MUST 显示推荐度：
  - auto → ⭐⭐⭐
  - int → ⭐⭐
  - str → ⭐⭐
  - sep_first → ⭐

### Requirement: 文档维护规范

lookup-cast-guide.md MUST 遵循项目文档治理规则：
- 不包含 `.gen.` 后缀（手工维护）
- 不使用 `<!-- BEGIN/END AUTOGEN -->` 注入块
- 内容变更不依赖 `just gen-docs` 重新生成

#### Scenario: 文档入口链接
- **WHEN** lookup-cast-guide.md 创建完成
- **THEN** usage-guide.md MUST 包含指向 lookup-cast-guide.md 的链接
