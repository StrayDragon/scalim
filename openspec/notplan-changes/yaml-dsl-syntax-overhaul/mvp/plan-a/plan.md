# Plan A (Recommended): sources-first + explicit refs + `output.select`

## One-liner

把 `main_source` 合并进 `sources`,用 `main: true` 标识主源;用 `joins` 的显式 `id/ref` 替代“只能 alias/内联 steps”;用 `output.select` 替代 `output.fields` 的对象身份解析。

## Target outcomes

- 不需要 YAML anchors/alias 才能写出正确配置(anchors 仅做可选复用)
- main/source/fields/relations/output 的入口更统一
- output 字段选择与覆写可以用显式 `ref` 完成,不再依赖 alias 身份

## Proposed shape (schema-level)

```yaml
name: <str>
description: <str?>

batch_size: <int|null?>
retry: <loader-retry?>

sources:
  <source_id>:
    main: <bool?>                # exactly one main=true
    loader: <python-ref>
    key: <str|[str,...]?>        # main source 可省略 key
    params: <template>
    order_by: <[field-ref]?>     # only for main source
    cache_mode: none|preload_forever?
    lookup_cast: {name: ...}?
    lookup_chunk_size: <int?>?
    normalize: {...}?
    retry: <loader-retry?>?
    fields:
      <field_id>:
        name: <str?>
        extract: <path?>         # current-row-relative
        value_cast: <enum?>?
        via: <join-ref?>?        # replaces relation alias; optional if unique path

joins:
  <join_id>:
    steps:
      - from: <source.field>
        to: <source.field>
        lookup_cast: {name: ...}?

derive:
  <field_id>:
    name: <str?>
    expr: <compute-expr>         # replaces compute (name chosen for直觉)
    call:                        # structured call_by (optional alternative)
      ref: <python-ref>
      kwargs: {<arg>: <field-ref|literal|$ctx.*>}

output:
  format: csv|excel
  path: <str?>
  streaming: <bool?>
  include_header: <bool?>
  header_fields_output_by: field_id|name
  select:
    - <field-ref>                # sugar
    - ref: <field-ref>           # object for overrides
      name: <str?>               # override display name

guardrails: <same-as-today?>
observability: <same-as-today?>
```

### Reference model (`field-ref`)

建议统一为以下三类:
- `orders.order_id` (source field)
- `customers.customer_name` (joined source field)
- `order_amount` (derived field)

输出/依赖/params/覆盖全部用这个 ref 语义,避免对象身份依赖。

## Params template calibration

保持现有 `$keys/$rows` 指令能力,但把 `$runtime.*` 从“字符串占位符”统一成指令节点(同时允许 shorthand):

- `ids: {$runtime: order_ids}` (推荐)
- `ids: "$runtime.order_ids"` (shorthand,可选)
- `ids: {$keys: {as: list}}`
- `rows: {$rows: {cache_mode: batch}}`

## Mapping from current DSL (one-step)

- `main_source` → `sources.<source_id>.main: true`
- `relations.<id>` → `joins.<id>`
- 字段 `relation: *alias` → 字段 `via: <join_id>`
- 顶层 `fields`(derived) → 顶层 `derive`
- `output.fields` → `output.select`:
  - alias entry → `ref: <source.field_id>` 或 `ref: <derived_id>`
  - 覆写键保持一致(例如 `name` 覆写)

## Pros / Cons

Pros:
- 语法更统一,不会把用户推向 alias 语义
- JSON Schema 更容易表达(大量对象身份相关规则可删除)
- 对 agent/editor 更友好(显式 ref 可稳定补全/跳转)

Cons:
- 是 breaking 变更,需要迁移工具与仓内示例全量升级
- compute 表达式若支持 `source.field` 语法,需要编译器/解析器升级(可先仅支持 derived ref + 显式 `ref(...)` helper)

