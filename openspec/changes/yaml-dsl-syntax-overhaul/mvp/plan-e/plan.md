# Plan E (Feasible): Minimal break / maximal pain reduction on current DSL

## One-liner

不推翻整体结构,在保持 `main_source/sources/relations/output` 形状基本不变的前提下,做一组“足够大但可快速落地”的语法校准,优先移除最反直觉的 alias/对象身份依赖。

## Proposed changes (breaking, but small surface area)

1) **relation 支持 string ref**
- 允许 `relation: orders_to_customers` 直接引用 `relations` 里的 id
- 保留 `relation: {steps: [...]}` 与 `relation: *alias`(兼容 anchors 用户)

2) **output.fields 支持 string list sugar**
- 允许 `output.fields: [order_id, order_date, order_amount]`
- 允许 `output.fields: [customers.customer_name, products.product_name]` 用 `source.field_id` 形式消歧
- 保留对象条目用于覆写(如 `name/value_cast/...`)

3) **顶层 derived `fields` 改名为 `derive`**
- 直接消除“顶层 fields 其实只允许派生字段”的误解源

4) **统一 runtime vars 与 directives 的表达**
- 允许 runtime var 用指令节点写法:
  - `ids: {$runtime: order_ids}`
- 同时保留 `$runtime.order_ids` 字符串 shorthand

## What stays the same

- `main_source`/`sources`/`relations` 的结构与语义保持一致
- `compute/call_by` 的语义与安全边界保持一致(只是换入口名/写法 sugar)
- guardrails/observability/retry/batch_size 等保持一致

## Why this is the “can ship” option

- 绝大多数改动在 validator/schema/解析层即可完成
- 对 IR/执行层影响较小(更多是引用解析与输出字段解析的简化)
- 能显著降低文档/skill 的复杂度,并为未来更激进方案提供迁移跳板

