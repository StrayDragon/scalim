## Context

outputs 支持多种输出模式：
1. **detail**: 明细数据输出
2. **where**: 条件过滤分发
3. **aggregate**: 聚合汇总输出

支持资源配置（resources.books/files）和复用机制（YAML merge / from），配置选项多。

## Goals / Non-Goals

**Goals:**
- 创建专题指南，清晰对比三种输出模式
- 说明 aggregate 算子的使用场景
- 解释资源绑定和复用机制

**Non-Goals:**
- 不修改现有语法行为
- 不新增或删除语法特性

## Decisions

### 文档结构

```
docs/doc/yaml-dsl/output-guide.md
├── 1. 输出模式概览
│   ├── 对比表格
│   └── 推荐度标注
├── 2. Detail 输出（⭐⭐⭐）
│   ├── 语法说明
│   ├── 字段列表配置
│   └── 示例
├── 3. Where 过滤（⭐⭐）
│   ├── 语法说明
│   ├── 条件表达式
│   ├── 分发到不同 sheet
│   └── 示例
├── 4. Aggregate 输出（⭐⭐）
│   ├── 语法说明
│   ├── group_by 配置
│   ├── 基础算子（count, sum, min, max）
│   ├── 高级算子（count_distinct, count_true, rank）
│   ├── guardrails（max_groups, max_distinct）
│   └── 示例
├── 5. 资源绑定
│   ├── resources.books/files 复用
│   ├── to.book / to.sheet 绑定
│   └── YAML merge 复用
├── 6. From 复用机制
│   ├── 继承字段集合
│   └── 继承容器配置
└── 7. 选择决策树
```

### 算子分组

- **基础算子**: count, sum, min, max（90% 场景）
- **高级算子**: count_distinct, count_true, rank（特定场景）

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| aggregate 算子过多难以记忆 | 按使用频率分组，重点讲解基础算子 |
| guardrails 配置复杂 | 提供默认值说明和推荐配置 |
| YAML merge 可读性差 | 推荐使用 from 复用机制 |

## Migration Plan

此变更不涉及代码迁移，纯文档变更。

## Open Questions

1. 是否需要为每种算子提供具体的计算示例？
2. guardrails 的默认值是否需要调整？
