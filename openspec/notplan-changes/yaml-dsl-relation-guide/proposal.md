## Why

relation 关联语法支持三种引用方式（string ref / YAML alias / inline steps），但缺少专题说明文档。用户在选择引用方式时常常困惑，不清楚各种方式的适用场景和性能影响。

## What Changes

创建 YAML DSL relation 关联语法专题指南，包含：

1. **三种引用方式对比**
   - string ref (`relation: orders_to_customers`)
   - YAML alias (`relation: *orders_to_customers`)
   - inline steps (`relation: {steps: [...]}`)

2. **使用场景说明**
   - string ref：默认推荐，LSP 友好，支持跨文件引用
   - YAML alias：用于 _templates 复用
   - inline steps：一次性关联，不准备复用

3. **推荐度标注**
   - string ref → ⭐⭐⭐（默认推荐）
   - YAML alias → ⭐⭐（_templates 复用场景）
   - inline steps → ⭐（一次性场景）

4. **性能考虑**
   - named relations vs inline relations 的性能对比
   - 复用机制的性能优势
   - 何时选择哪种方式

## Capabilities

### New Capabilities
- `yaml-dsl-relation-guide`: 新增 relation 关联语法专题指南文档

### Modified Capabilities
- 无（此变更为纯文档变更）

## Impact

- 新增文档：`docs/doc/yaml-dsl/relation-guide.md`
- 更新：`docs/doc/yaml-dsl/usage-guide.md` 添加链接
- 无代码变更
- 无行为变更
