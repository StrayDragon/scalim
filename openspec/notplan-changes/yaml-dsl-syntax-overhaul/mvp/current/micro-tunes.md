# Micro-tunes: improvements that reduce pain even without a full rewrite

本清单用于给 review 一个“低成本可落地”的对照组: 即使最终选择激进方案,其中一部分也可以先落地减痛。

## 1) relation 引用允许字符串 ref (替代 alias-only)

当前 `relation` 只能 steps 对象或 YAML alias,不允许 `relation: <relation_id>`。

微调提案:
- 允许 `relation: <relation_id>` (string)
- 同时保留 `relation: {steps: [...]}` 与 `relation: *alias`
- validator 在 string 模式下做:
  - 必须存在同名 `relations.<id>`
  - steps 起止校验与 chain 校验不变

收益:
- 大幅降低 YAML anchors 学习/使用门槛


> 同意, 可以支持, 另外还有哪些其他类似场景也可以罗列出来支持, 因为我们大量的alias 场景其实挺依赖 pyyaml的解析逻辑行为的 所以最好也支持 string ref 来兜底之后如果升级解析器导致兼容性问题

## 2) output.fields 引入更直觉的 string sugar

当前 `output.fields` 不支持纯字符串(必须对象或 alias),导致“最简单场景也得写一堆对象”。

微调提案:
- 允许:
  - `output.fields: [order_id, order_date, customer_name]` 作为 `field_id` 列表 sugar
  - `output.fields: [orders.order_id, customers.customer_name]` 作为显式 source.field_id sugar(用于消歧)
- 仍保留对象条目用于覆写 name/relation/value_cast 等

收益:
- 让 80% 场景写法更短,同时保留高级覆写能力

> 同意, 可以支持

## 3) derived 字段入口改名以减少误解

当前顶层 `fields` 实际只允许派生字段(源字段写在 sources/main_source),这对读者非常反直觉。

微调提案:
- 把顶层 `fields` 重命名为 `derived_fields`
- schema 与 validator 直接体现“这里只有派生字段”

收益:
- 不改变能力,但显著降低误写与文档解释成本

> 这一步修改后需要统一适配相关使用的点 请一步到位升级 之后 我们可以将 fields 作为跨多数据源多需求的字段处理的专有入口

## 4) `$runtime` 占位符与 `$keys/$rows` 指令统一形态

当前 `$runtime.*` 是字符串占位符,而 `$keys/$rows` 是映射指令节点。

微调提案:
- 允许 runtime var 也用指令节点表达:
  - `ids: {$runtime: order_ids}`
- 同时保留 `$runtime.order_ids` 作为 shorthand(可选)
> 这个保留需要评估下 是不是需要一步到位迁移(以不支持 避免维护复杂)

收益:
- params 语言更一致,更易在 schema hover 中解释

> 支持

## 5) 强化“field_id vs data_key”的静态提示与自动修复建议

微调提案:
- 当 relation steps 写了 data_key(不在声明字段与 key 中)时,错误消息附带:
  - 最可能的 field_id(s) 建议
  - 可直接照抄的修复片段

收益:
- 降低迁移/排错成本,对现有语法也增益

> 支持
