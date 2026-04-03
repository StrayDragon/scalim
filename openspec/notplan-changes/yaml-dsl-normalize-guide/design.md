## Context

normalize 支持多种预置类型：
1. **index_by_key**: 建立索引映射
2. **take_first**: 一对多转一对一
3. **project_fields**: 字段投影/重命名
4. **map_values**: 批量应用转换

支持链式调用（steps）和 call_by 扩展点，配置复杂度高。

## Goals / Non-Goals

**Goals:**
- 创建专题指南，清晰对比四种类型
- 说明链式调用的使用场景
- 提供常见组合模式的示例

**Non-Goals:**
- 不修改现有语法行为
- 不新增或删除语法特性

## Decisions

### 文档结构

```
docs/doc/yaml-dsl/normalize-guide.md
├── 1. 四种预置类型概览
│   ├── 对比表格
│   └── 推荐度标注
├── 2. Index_By_Key（⭐⭐⭐）
│   ├── 行为说明
│   ├── on_conflict 策略
│   └── 示例
├── 3. Take_First（⭐⭐）
│   ├── 行为说明
│   ├── on_empty 策略
│   └── 示例
├── 4. Project_Fields（⭐⭐）
│   ├── 行为说明
│   ├── on_missing 策略
│   └── 示例
├── 5. Map_Values + Steps（⭐）
│   ├── 链式调用说明
│   ├── 组合模式示例
│   └── call_by 扩展点
├── 6. 常见组合模式
│   ├── take_first + project_fields
│   └── 其他组合
└── 7. 选择决策树
```

### 复杂度分层

- **基础**: index_by_key（单级索引）
- **中级**: take_first / project_fields（简单转换）
- **高级**: map_values + steps（复杂转换）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 链式调用配置过于复杂 | 提供常见组合模式的预制示例 |
| 用户过度使用高级功能 | 标注推荐度，说明大部分场景用基础功能即可 |

## Migration Plan

此变更不涉及代码迁移，纯文档变更。

## Open Questions

1. 是否需要提供「常见转换模式」的代码片段库？
2. call_by 扩展点是否需要单独的文档章节？
