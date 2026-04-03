## Why

lookup_cast 支持四种模式（auto / int / str / sep_first），其中 sep_first 有特定的使用场景和性能风险（N+1 查询问题），缺少专题说明文档。用户可能在不了解性能影响的情况下误用。

## What Changes

创建 YAML DSL lookup_cast 语法专题指南，包含：

1. **四种模式对比**
   - auto：默认行为，自动归一化
   - int：显式整数转换
   - str：显式字符串转换
   - sep_first：CSV 多值 key 处理

2. **使用场景说明**
   - auto：大部分场景，可省略不写
   - int/str：上游类型不一致时的显式转换
   - sep_first：处理 "1,2,3" 格式的多值 key

3. **性能警告**
   - sep_first 的 N+1 查询风险
   - 何时应在 loader 中预处理
   - 替代方案说明

4. **推荐度标注**
   - auto → ⭐⭐⭐（默认推荐）
   - int → ⭐⭐（特定类型转换场景）
   - str → ⭐⭐（特定类型转换场景）
   - sep_first → ⭐（高级场景，注意性能）

## Capabilities

### New Capabilities
- `yaml-dsl-lookup-cast-guide`: 新增 lookup_cast 语法专题指南文档

### Modified Capabilities
- 无（此变更为纯文档变更）

## Impact

- 新增文档：`docs/doc/yaml-dsl/lookup-cast-guide.md`
- 更新：`docs/doc/yaml-dsl/usage-guide.md` 添加链接
- 无代码变更
- 无行为变更
