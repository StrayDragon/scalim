## Context

当前讨论中最没有争议的一类问题,是 schema/runtime 自身存在明确漂移:

- workflow runtime 对 `workflow.resources` 是强结构解析,但 schema 因复用建模把 `$import` 暴露了出来
- demand/workflow schema 都存在 numeric constraints typing holes

这些问题本身不是“产品策略选择”,而是稳定性与可信度问题。它们适合作为独立 change 尽快厘清。

## Goals

- 建立 workflow schema/runtime 对齐的明确边界
- 让 JSON Schema 的数值约束具备真实约束力
- 为后续 change 提供可依赖的 drift gate

## Non-Goals

- 不决定 demand imports 的主线允许范围
- 不决定哪些 runtime policy 最终迁出 YAML
- 不设计 editor/LSP API

## Design Direction

### 1. Workflow `resources` 采用 runtime-first 对齐

对 `workflow.resources` 而言,当前真实契约应以 runtime parser 为准:

- runtime 未实现 imports expansion
- runtime 仅支持其显式声明的资源结构

因此本 change 的推荐方向不是“补 runtime 以匹配 schema”,而是“收紧 schema 以匹配 runtime”,并补齐明确的 migration hint。

### 2. Numeric constraints 采用生成期 fail-fast

凡是 schema 中声明:

- `minimum`
- `maximum`
- `exclusiveMinimum`
- `exclusiveMaximum`

都必须同时声明:

- `type: number`,或
- `type: integer`

推荐在 schema generation 阶段直接失败,而不是靠测试用例事后兜底。

这里的口径需要保守:

- 只有在生成器能够明确判定“这是无效 numeric constraint”时才直接报错
- 对边界不够明确、可能是 schema DSL 表达差异的问题,不在这一轮扩大为新的 fail-fast 范围

也就是说,这个 change 先修“特别确信是错误”的 typing hole,而不是借机引入更激进的 schema 规范化。

### 3. Drift gate 只覆盖高价值关键面

第一阶段 drift gate 不追求“全 schema/runtime 自动等价证明”,而只覆盖最关键、最容易误导用户的区域:

- `workflow.resources` allowed keys
- numeric constraints typing

等这些关键点稳定后,再考虑是否扩大覆盖面。

## Resolved Decisions

### 1. workflow drift gate 第一阶段只覆盖 `allowed keys`

当前优先级最高的 drift,是“schema 说可以写, runtime 却根本不认”的情况。

典型例子就是:

- schema 暴露了 `workflow.resources.books.<id>.$import`
- runtime parser / compiler 并不支持这类 imports expansion

这类问题会直接误导编辑器校验与文档示例,因此第一阶段 gate 先盯住:

- `workflow.resources` allowed keys drift

`required/default` drift 也重要,但不作为本 change 的首轮阻断范围。

### 2. numeric typing 校验以生成器内 fail-fast 为主

当前结论是:

- 主校验放在 schema generation 内部
- `just qa` / 相关检查脚本再补一层兜底

这样可以保证:

- schema DSL 一旦写出明显无效的 numeric constraint,错误最早暴露
- 即使未来有人绕过常规生成入口,仓库级检查也还能拦住


## Dependencies

- 这个 change 可先于其余拆分 change 审核
- `c999-yaml-dsl-lsp` 应依赖本 change 的结果,以避免基于不可信 schema 开发 editor 体验
