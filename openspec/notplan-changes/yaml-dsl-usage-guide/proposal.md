## Why

当前 YAML DSL 文档侧重于语法参考说明，缺少语法使用场景和选择指南。用户在面对多种语法选项时（如 relation 的三种引用方式、lookup_cast 的四种模式、normalize 的多种类型）难以做出合适的选择，增加了学习成本和配置复杂度。

## What Changes

创建新的 YAML DSL 使用指南文档，提供：

1. **语法分层说明**
   - 核心语法：覆盖 90% 使用场景
   - 扩展语法：高级数据处理场景
   - 专家语法：特殊边界场景

2. **语法选择决策树**
   - relation 引用方式选择（string ref / YAML alias / inline steps）
   - 数据转换方式选择（lookup_cast / normalize / value_cast）
   - 输出配置方式选择（resources + outputs / 内联声明）

3. **最佳实践与反模式**
   - 推荐的命名约定
   - 配置复用模式（imports / _templates）
   - 常见反模式说明

4. **语法推荐度标注**
   - 为每种语法标注推荐度（⭐⭐⭐ / ⭐⭐ / ⭐）
   - 说明每种语法的使用场景和注意事项

## Capabilities

### New Capabilities
- `yaml-dsl-usage-guide`: 新增 YAML DSL 使用指南文档，提供语法选择建议和最佳实践

### Modified Capabilities
- 无（此变更为纯文档变更，不涉及行为规范修改）

## Impact

- 新增文档文件：`docs/doc/yaml-dsl/usage-guide.md`
- 更新：`docs/doc/yaml-dsl/user-guide.md` 添加使用指南入口链接
- 无代码变更
- 无行为变更
- 无向后兼容问题
