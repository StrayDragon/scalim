## Why

`guardrails`、`retry`、`batch_size`、部分 `failure_policy` 一起构成了当前 YAML DSL 中最模糊的一层:

- 一方面,它们看起来像“需求行为的一部分”
- 另一方面,它们又明显受环境、性能预算、生产/调试策略影响

其中 `guardrails` 尤其敏感:

- 某些护栏会引入额外性能损耗
- 某些环境希望严格 fail-fast,而另一些环境更希望继续运行

这说明它们需要被作为“runtime policy boundary”单独讨论,不能继续和其它专题混在一起一笔带过。

## What Changes

- 单独澄清哪些 runtime policy 应从 YAML 主线迁到 Python / CLI
- 对最难的部分,尤其 `guardrails`,明确决策空间与推荐方向
- 为后续 specs 提供更聚焦的批准基线

## Scope

包括:
- `guardrails.*`
- `retry.*`
- `batch_size`
- demand / workflow 上与 runtime policy 强相关的 `failure_policy`
- workflow `options` 中明显环境敏感的 diagnostics / staging / wait 类入口

不包括:
- `observability.*` 的迁出策略
- `write_defaults` / `outputs[*].write` 的 SSOT
- demand imports 的最终 authoring 允许范围

## Expected Outcome

- 我们会得到一份更清晰的 runtime policy 边界设计,而不是继续把它们混在 authoring DSL 中
- `guardrails` 的环境/性能语义会有单独结论
