## Why

normalize 支持多种预置类型（index_by_key / take_first / project_fields / map_values）和链式调用（steps），配置复杂度高。缺少专题说明文档，用户难以理解各种类型的使用场景和组合方式。

## What Changes

创建 YAML DSL normalize 语法专题指南，包含：

1. **四种预置类型对比**
   - index_by_key：建立索引映射
   - take_first：一对多转一对一
   - project_fields：字段投影/重命名
   - map_values：批量应用转换

2. **链式调用说明**
   - steps 数组的使用
   - 组合模式（如 take_first + project_fields）
   - call_by 扩展点

3. **使用场景说明**
   - index_by_key：最常见的索引建立
   - take_first：处理一对多关系
   - project_fields：字段选择和重命名
   - map_values + steps：复杂转换场景

4. **推荐度标注**
   - index_by_key → ⭐⭐⭐（默认推荐）
   - take_first → ⭐⭐（一对多场景）
   - project_fields → ⭐⭐（字段投影场景）
   - map_values + steps → ⭐（高级场景）

## Capabilities

### New Capabilities
- `yaml-dsl-normalize-guide`: 新增 normalize 语法专题指南文档

### Modified Capabilities
- 无（此变更为纯文档变更）

## Impact

- 新增文档：`docs/doc/yaml-dsl/normalize-guide.md`
- 更新：`docs/doc/yaml-dsl/usage-guide.md` 添加链接
- 无代码变更
- 无行为变更
