# Current YAML DSL: Inventory & Pain Points (for redesign)

本目录用于把“当前 DSL 的全量语法能力”收敛成 review 需要的可读摘要,帮助对齐重构目标与评估维度。

## Canonical references (do not fork)

- Full syntax catalog (generated): `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`
- Canonical full example (generated export): `artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`
- Schema: `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- Semantic validator: `src/scalim/dsl/by_yaml/config_parsing/validator.py` + `validators/**`

## Structure summary (today)

Top-level:

- `name` / `description`
- `_templates` (anchors/alias 模板集合;其中 `_templates.retry.*` 有语义)
- `batch_size` + `retry`
- `main_source` (required)
- `sources` (lookup sources)
- `relations` (relation path templates)
- `fields` (derived only; `compute`/`call_by`)
- `output` (file output + output.fields 选择/覆写)
- `guardrails` + `observability`

Main source:

```yaml
main_source:
  source_id: orders
  loader: "pkg.mod:load_orders"
  params: {...}        # 允许静态值与 $runtime.*; 禁止 $keys/$rows
  order_by: [...]      # 仅允许 main_source.fields 中声明的 field_id
  fields: {...}        # 源字段(禁止 compute/call_by)
```

Lookup source:

```yaml
sources:
  customers:
    loader: "pkg.mod:load_customers"
    key: customer_id | [k1, k2]
    params: {...}      # 允许 $runtime.* 与 $keys/$rows(但 preload_forever 禁止 directives)
    fields: {...}      # 源字段(多为 relation 字段)
    cache_mode: none|preload_forever
    lookup_cast: {name: int|str|auto...}
    lookup_chunk_size: <int>
    normalize: {kind: index_by_key, key_field: ..., on_conflict: ...}
    retry: {...}
```

Derived field:

```yaml
fields:
  order_amount:
    name: 订单金额
    compute: "round(quantity * unit_price * discount_rate, 2)"
```

Relation:

```yaml
relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id
        lookup_cast: {name: int}
```

Output selection:

```yaml
output:
  format: csv
  path: ./out.csv
  fields:
    - *order_id                      # alias (对象身份)
    - {field_id: quantity, name: 数量} # 显式选择器 + 覆写
    - {field: category_id, source: products} # 按 data_key 选择(需要 source 消歧)
```

## Pain points (root causes)

1) **多入口导致“哪里该写什么”不直觉**
- 源字段与派生字段的声明位置被硬拆开(`main_source.fields/sources.*.fields` vs 顶层 `fields`)
- relation 既可 `relations` 定义也可字段内联,但 ref 语义不统一

2) **对象身份依赖(anchors/alias)是最大反直觉来源**
- `output.fields` 的 alias 解析依赖对象身份(`AliasIndex(id(obj))`)
- YAML merge(`<<`) 会破坏身份,引入额外选择器规则与大量文档说明

3) **relation 不能用字符串引用**
- 字段 `relation` 不允许 `relation: orders_to_customers` 字符串,只能 alias 或内联 steps
- 这强迫用户理解 YAML anchors 的“定义在前”语义

4) **field_id vs data_key 的双命名体系**
- steps 必须写 field_id,而字段 extract 又可能 rename/nested
- 诊断需要大量“你写的是 data_key,应该写 field_id”的规则说明

5) **params 模板语言不统一**
- `$runtime.*` 是字符串占位符
- `$keys/$rows` 是映射指令节点
- 并且对 main/source/cache_mode 有不同限制

这些痛点是 plan-a..plan-f 的评估基线: 新语法必须显著减少上述复杂度,且不牺牲现有能力边界。

