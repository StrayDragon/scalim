## Why

outputs 支持多种输出模式（detail / where 过滤 / aggregate）和资源配置（resources），配置选项多。缺少专题说明文档，用户难以理解各种模式的使用场景和配置方式。

## What Changes

创建 YAML DSL output 输出配置专题指南，包含：

1. **输出模式对比**
   - detail 输出：明细数据
   - where 过滤：条件分发
   - aggregate 输出：聚合汇总

2. **资源绑定说明**
   - resources.books/files 复用
   - to.book / to.sheet 绑定
   - YAML merge 复用模式

3. **aggregate 算子详解**
   - 基础算子：count, sum, min, max
   - 高级算子：count_distinct, count_true, rank
   - guardrails：max_groups, max_distinct

4. **from 复用机制**
   - 继承字段集合
   - 继承容器配置

5. **推荐度标注**
   - detail → ⭐⭐⭐（默认推荐）
   - where → ⭐⭐（条件分发场景）
   - aggregate → ⭐⭐（聚合汇总场景）

## Capabilities

### New Capabilities
- `yaml-dsl-output-guide`: 新增 output 输出配置专题指南文档

### Modified Capabilities
- 无（此变更为纯文档变更）

## Impact

- 新增文档：`docs/doc/yaml-dsl/output-guide.md`
- 更新：`docs/doc/yaml-dsl/usage-guide.md` 添加链接
- 无代码变更
- 无行为变更
