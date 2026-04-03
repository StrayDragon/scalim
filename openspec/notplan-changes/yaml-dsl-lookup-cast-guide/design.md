## Context

lookup_cast 支持四种模式：
1. **auto**: 默认行为，自动归一化
2. **int**: 显式整数转换
3. **str**: 显式字符串转换
4. **sep_first**: CSV 多值 key 处理

其中 sep_first 有特殊的性能特征（可能导致 N+1 查询），需要专题说明。

## Goals / Non-Goals

**Goals:**
- 创建专题指南，清晰对比四种模式
- 重点说明 sep_first 的性能风险
- 提供何时应在 loader 中预处理的建议

**Non-Goals:**
- 不修改现有语法行为
- 不新增或删除语法特性

## Decisions

### 文档结构

```
docs/doc/yaml-dsl/lookup-cast-guide.md
├── 1. 四种模式概览
│   ├── 对比表格
│   └── 推荐度标注
├── 2. Auto（⭐⭐⭐）
│   ├── 行为说明
│   ├── 使用场景（大部分场景）
│   └── float key 拒绝策略
├── 3. Int / Str（⭐⭐）
│   ├── 行为说明
│   ├── 使用场景（上游类型不一致）
│   └── 示例
├── 4. Sep_First（⭐）
│   ├── 行为说明
│   ├── 使用场景（CSV 多值 key）
│   ├── 性能警告（N+1 风险）
│   └── 替代方案（loader 预处理）
├── 5. 配置位置
│   ├── source 级别配置
│   └── step 级别配置
└── 6. 最佳实践
```

### 性能警告重点

**sep_first 的 N+1 问题**：
- 每个不同的 key 值都会触发一次 lookup
- 对于 "1,2,3" 格式的多值 key，可能需要多次查询
- 建议在 loader 中预处理为单独的行

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 过度强调性能问题导致用户不敢用 | 说明 sep_first 的适用场景，提供性能数据 |
| 替代方案不清晰 | 提供具体的 loader 预处理示例 |

## Migration Plan

此变更不涉及代码迁移，纯文档变更。

## Open Questions

1. 是否需要在 LSP 中为 sep_first 添加性能警告提示？
2. 是否有实际的性能测试数据可以引用？
