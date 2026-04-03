## Context

当前 YAML DSL 文档主要包含：
- 语法参考（schema hover 文档）
- 示例代码（tests/fixtures/、notebooks/）
- 架构说明（ARCH.md）

缺少使用场景指导，用户在面对多种语法选项时难以做出合适选择。例如：
- relation 支持三种引用方式（string ref / YAML alias / inline steps）
- lookup_cast 支持四种模式（auto / int / str / sep_first）
- normalize 支持多种类型和链式调用

## Goals / Non-Goals

**Goals:**
- 创建易读的语法使用指南，帮助用户快速选择合适的语法
- 为每种语法标注推荐度和使用场景
- 提供最佳实践和常见反模式说明
- 确保文档易于维护和更新

**Non-Goals:**
- 不修改现有语法行为
- 不新增或删除语法特性
- 不改变现有文档结构

## Decisions

### 文档组织结构

采用分层结构，按使用频率和复杂度组织：

```
docs/doc/yaml-dsl/usage-guide.md
├── 1. 语法分层概览
│   ├── 核心语法（90% 场景）
│   ├── 扩展语法（高级场景）
│   └── 专家语法（特殊场景）
├── 2. 语法选择决策树
│   ├── relation 引用方式
│   ├── 数据转换方式
│   └── 输出配置方式
├── 3. 语法详解与推荐度
│   ├── relation 语法
│   ├── lookup_cast 语法
│   ├── normalize 语法
│   └── value_cast 语法
├── 4. 最佳实践
│   ├── 命名约定
│   ├── 配置复用模式
│   └── 常见反模式
└── 5. 参考链接
```

### 推荐度标注

使用三级推荐度：
- ⭐⭐⭐：默认推荐，覆盖大部分场景
- ⭐⭐：特定场景适用
- ⭐：高级或特殊场景

### 文档维护策略

- usage-guide.md 为手工维护文档
- 语法参考保持由 schema 生成（.gen.md 文件）
- user-guide.md 添加指向 usage-guide.md 的入口链接

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 文档与实现脱节 | 定期对照 schema 和示例代码审查 |
| 推荐度主观性 | 基于实际使用场景和用户反馈调整 |
| 维护成本增加 | 将推荐度标注集成到 LSP hover 文档 |

## Migration Plan

此变更不涉及代码迁移：
1. 创建 usage-guide.md
2. 在 user-guide.md 添加入口链接
3. 可选：将推荐度标注迁移到 schema hover 文档

## Open Questions

1. 是否需要为语法添加「使用频率」统计？
2. 推荐度是否需要在 LSP 中体现（如 warning）？
3. 是否需要提供「语法迁移工具」（如 inline steps → named relation）？
