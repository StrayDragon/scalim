# Plan B: SQL-ish `query` (from/join/select) as the DSL backbone

## One-liner

把 YAML DSL 组织为结构化查询: `datasets` 描述 loader 与输入,`query` 描述 join 与 select,派生字段直接写在 `select` 中。

## Why this might be more intuitive

- 大多数报表作者对 “from/join/select” 有天然直觉
- 不需要额外理解 “relations vs fields vs output.fields” 的多入口
- join 与派生字段都归一到 query 里,文档与 editor 补全更聚焦

## Proposed shape (schema-level)

```yaml
name: <str>
description: <str?>

datasets:
  <id>:
    loader: <python-ref>
    key: <str|[str,...]?>        # lookup dataset required
    params: <template>
    fields:                       # optional metadata (name/extract/cast)
      <field_id>: {...}

query:
  from: <dataset-id>              # main dataset
  joins:
    - to: <dataset-id>
      type: left                  # left join semantics
      on:
        - from: <dataset.field_id>
          to: <dataset.field_id>
          lookup_cast: {name: ...}?
  select:
    - <dataset.field_id>          # sugar (as=field_id)
    - ref: <dataset.field_id>     # object form for overrides
      as: <out_id?>
      name: <display_name?>
    - expr: <compute-expr>        # derived in select
      as: <out_id>
      name: <display_name?>
    - call:                       # structured call in select
        ref: <python-ref>
        kwargs: {...}
      as: <out_id>

output:
  format: csv|excel
  path: <str?>
  streaming: <bool?>

observability/guardrails/retry/...: <same-as-today?>
```

## Mapping from current DSL (one-step)

- `main_source` + `sources` → `datasets` + `query.from` / `query.joins`
- `relations` → `query.joins` (join steps 直接内联)
- 顶层 `fields`(derived) → `query.select` 里的 `expr/call`
- `output.fields` → `query.select`(输出字段顺序由 select 本身决定)

## Pros / Cons

Pros:
- 结构最直觉,把“报表=一条查询”表达得很直接
- 大幅减少顶层模块数量(降低心智负担)

Cons:
- 对 “复用 join path/字段模板” 的需求需要额外机制(可选引入 `joins:` templates)
- 如果未来引入更复杂的 DAG(多阶段输出/中间产物),query 模型可能不够表达力

