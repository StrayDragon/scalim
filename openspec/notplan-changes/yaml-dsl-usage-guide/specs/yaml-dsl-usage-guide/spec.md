## ADDED Requirements

### Requirement: 语法分层说明

使用指南文档 MUST 将 YAML DSL 语法按使用频率和复杂度分为三个层次：
- **核心语法**：覆盖 90% 常见场景
- **扩展语法**：高级数据处理场景
- **专家语法**：特殊边界场景

#### Scenario: 用户快速定位所需语法
- **WHEN** 用户打开使用指南
- **THEN** 用户 MUST 能通过语法分层快速找到适合其场景的语法

### Requirement: 语法推荐度标注

使用指南文档 MUST 为每种语法标注三级推荐度：
- ⭐⭐⭐：默认推荐，覆盖大部分场景
- ⭐⭐：特定场景适用
- ⭐：高级或特殊场景

#### Scenario: 用户选择 relation 引用方式
- **WHEN** 用户需要配置 relation
- **THEN** 文档 MUST 显示三种引用方式的推荐度：
  - `relation: <relation_id>` → ⭐⭐⭐
  - `relation: *alias` → ⭐⭐
  - `relation: {steps: [...]}` → ⭐

#### Scenario: 用户选择 lookup_cast 模式
- **WHEN** 用户需要配置 lookup_cast
- **THEN** 文档 MUST 显示四种模式的推荐度：
  - `auto` → ⭐⭐⭐（默认可省略）
  - `int` → ⭐⭐
  - `str` → ⭐⭐
  - `sep_first` → ⭐

### Requirement: 语法选择决策树

使用指南文档 MUST 提供语法选择决策树，帮助用户根据场景选择合适的语法。

#### Scenario: 用户选择 relation 引用方式
- **WHEN** 用户需要配置关联关系
- **THEN** 决策树 MUST 引导用户：
  - 关联是否需要复用？是 → 使用 string ref
  - 是否在 _templates 中复用？是 → 使用 YAML alias
  - 是否为一次性关联？是 → 使用 inline steps

#### Scenario: 用户选择数据转换方式
- **WHEN** 用户需要转换数据
- **THEN** 决策树 MUST 引导用户：
  - 是否为 key 归一化？是 → lookup_cast
  - 是否为 whole-result 转换？是 → normalize
  - 是否为字段级类型转换？是 → value_cast

### Requirement: 使用场景说明

使用指南文档 MUST 为每种语法提供清晰的使用场景说明。

#### Scenario: 理解 sep_first 的使用场景
- **WHEN** 用户阅读 lookup_cast.sep_first 说明
- **THEN** 文档 MUST 说明：
  - 场景：处理 CSV 多值 key（如 `"1,2,3"`）
  - 示例：按分隔符截取首段后再归一化
  - 注意事项：⭐ 高级场景，N+1 问题风险

#### Scenario: 理解 normalize.map_values 的使用场景
- **WHEN** 用户阅读 normalize.map_values 说明
- **THEN** 文档 MUST 说明：
  - 场景：复杂的链式数据转换
  - 示例：take_first + project_fields 组合
  - 注意事项：⭐ 高级场景，可考虑 call_by

### Requirement: 最佳实践与反模式

使用指南文档 MUST 包含最佳实践章节，说明推荐做法和常见反模式。

#### Scenario: 用户学习命名约定
- **WHEN** 用户阅读命名约定章节
- **THEN** 文档 MUST 提供：
  - 推荐的命名模式（如 `<entity>_<field>`）
  - 一致性建议（relation 命名与 field 命名对应）
  - 示例对比

#### Scenario: 用户学习配置复用模式
- **WHEN** 用户学习如何复用配置
- **THEN** 文档 MUST 说明：
  - imports vs _templates 的选择
  - 跨文件复用使用 imports
  - 文件内复用使用 _templates

#### Scenario: 用户识别反模式
- **WHEN** 用户阅读反模式章节
- **THEN** 文档 MUST 说明：
  - 过度使用 inline steps（应优先使用 named relations）
  - 重复的配置（应使用复用机制）
  - 不必要的复杂转换（应在 loader 中处理）

### Requirement: 参考链接

使用指南文档 MUST 提供相关文档的参考链接。

#### Scenario: 用户深入了解语法细节
- **WHEN** 用户需要了解语法的完整说明
- **THEN** 文档 MUST 提供到：
  - schema hover 文档的链接
  - 示例代码的链接
  - 架构文档的链接

### Requirement: 文档维护规范

usage-guide.md MUST 遵循项目文档治理规则：
- 不包含 `.gen.` 后缀（手工维护）
- 不使用 `<!-- BEGIN/END AUTOGEN -->` 注入块
- 内容变更不依赖 `just gen-docs` 重新生成

#### Scenario: 文档内容更新
- **WHEN** 语法行为发生变化
- **THEN** 维护者 MUST 手工更新 usage-guide.md 中的相关说明
- **AND** 保持与 schema hover 文档的一致性

#### Scenario: 文档入口链接
- **WHEN** usage-guide.md 创建完成
- **THEN** user-guide.md MUST 包含指向 usage-guide.md 的链接
- **AND** 链接位置应在文档顶部或明显的导航区域
