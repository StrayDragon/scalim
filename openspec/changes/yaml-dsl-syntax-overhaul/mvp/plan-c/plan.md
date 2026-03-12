# Plan C: Explicit pipeline DAG (`pipeline` steps)

## One-liner

把 YAML DSL 从“配置对象集合”改成“显式步骤序列”: source/load、join、derive、output 都是一个 step,用 `id` 连接依赖,天然对应 DAG/可视化/调度。

## Proposed shape (schema-level)

```yaml
name: <str>
description: <str?>

pipeline:
  - id: <step-id>
    kind: source | lookup | join_project | derive | output | ...
    ... kind-specific fields ...

guardrails/observability/retry/batch_size: <optional global defaults>
```

### Step kinds (MVP subset)

- `kind: source`
  - `loader/params/order_by/fields`
- `kind: lookup`
  - `loader/key/params/cache_mode/lookup_cast/fields`
- `kind: join_project`
  - `from: <source-step-id>`
  - `joins: [...]` (each join has `to` + `on` list)
  - `select: [...]` (the projected columns)
- `kind: derive`
  - `from: <join_project-step-id>`
  - `fields: {<id>: {expr|call}}`
- `kind: output`
  - `from: <derive-step-id>`
  - `format/path/streaming/select`

## Why it can simplify things

- 不需要单独的 `relations`/`fields`/`output.fields` 入口: join/derive/output 都在 pipeline 里
- 每一步的输入/输出是显式的,错误路径更容易定位(指向 step.id)
- 对未来多输出/中间产物/调度策略扩展更自然

## Trade-offs

- 写法更长,对简单报表可能显得“工程化”
- schema 与文档需要解释 step kinds,但一旦掌握后结构更统一

## Mapping from current DSL (one-step)

- `main_source` → 第一个 `kind: source` step
- `sources.*` → 若干 `kind: lookup` steps
- `relations + field.relation` → `kind: join_project` step 的 `joins`
- 顶层 derived `fields` → `kind: derive` step
- `output` → `kind: output` step

