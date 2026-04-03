## Context

relation 关联语法支持三种引用方式：
1. **string ref**: `relation: orders_to_customers`
2. **YAML alias**: `relation: *orders_to_customers`
3. **inline steps**: `relation: {steps: [...]}`

当前文档缺少对这些方式的系统对比，用户难以选择合适的引用方式。

## Goals / Non-Goals

**Goals:**
- 创建专题指南，清晰对比三种引用方式
- 为每种方式标注推荐度和使用场景
- 说明性能考虑和最佳实践

**Non-Goals:**
- 不修改现有语法行为
- 不新增或删除语法特性

## Decisions

### 文档结构

```
docs/doc/yaml-dsl/relation-guide.md
├── 1. 三种引用方式概览
│   ├── 对比表格
│   └── 推荐度标注
├── 2. String Ref（⭐⭐⭐）
│   ├── 语法说明
│   ├── 使用场景
│   ├── 优势：LSP 友好、跨文件引用
│   └── 示例
├── 3. YAML Alias（⭐⭐）
│   ├── 语法说明
│   ├── 使用场景（_templates 复用）
│   ├── 优势：YAML 原生复用
│   └── 示例
├── 4. Inline Steps（⭐）
│   ├── 语法说明
│   ├── 使用场景（一次性关联）
│   ├── 限制：不可复用
│   └── 示例
├── 5. 性能考虑
│   ├── Named vs Inline
│   └── 复用机制
└── 6. 选择决策树
```

### 推荐度原则

- **string ref (⭐⭐⭐)**: 默认推荐，适用于 90% 场景
- **YAML alias (⭐⭐)**: 仅用于 _templates 复用
- **inline steps (⭐)**: 仅用于不准备复用的一次性关联

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 用户过度使用 inline steps | 在文档中明确标注推荐度 |
| YAML alias 与 string ref 混淆 | 说明各自的适用场景 |
| 性能建议不准确 | 基于实际测试和实现细节 |

## Migration Plan

此变更不涉及代码迁移，纯文档变更。

## Open Questions

1. 是否需要在 LSP 中为 inline steps 添加警告提示？
2. 是否需要提供「inline steps → named relation」的自动迁移工具？
