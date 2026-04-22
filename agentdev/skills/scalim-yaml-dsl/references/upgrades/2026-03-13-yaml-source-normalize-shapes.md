# 2026-03-13: yaml-source-normalize-shapes

## 变更摘要

本批次扩展 `sources.<id>.normalize` 的声明式能力,用于减少“lookup 小表/维表”场景的 Python wrapper:

- 新增 `normalize.take_first`
- 新增 `normalize.project_fields`
- 新增 `normalize.map_values`(values pipeline)
- 新增受控扩展点 `normalize.call_by`(whole-result `Mapping -> Mapping`,受 allowlist 约束)

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-12-yaml-source-normalize-shapes/`

对应主规范(节选):
- `openspec/specs/yaml-source-normalize/spec.md`
- `openspec/specs/yaml-dsl-schema/spec.md`

下游同步盘点:
- 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）

## `normalize.take_first`

用于将“多条候选”归一化为“单条”:

- 输入形状: `mapping[key -> list[row]]`
- 输出形状: `mapping[key -> row]`

```yaml
normalize:
  take_first:
    on_empty: miss  # miss|null|error
```

注意:
- 顶层 `list[row]` 场景不属于 `take_first` 的职责,仍应使用 `index_by_key` + `on_conflict`

## `normalize.project_fields`

用于对 row 或 nested mapping 做投影/重命名,并支持 int-key path 与 `from_key` 注入:

```yaml
normalize:
  project_fields:
    on_missing: error  # error|null
    fields:
      order_id: {from_key: true}
      customer_level: {extract: "[1].clearn_reason_level"}
      operation_level: {extract: "[2].clearn_reason_level"}
      review_status: {extract: review_status}
```

要点:
- `fields` 的 key 为输出字段名(天然完成 rename)
- `extract` 的语法与字段级 `extract` 一致(支持 int-key path,例如 `"[1].x"`)

## `normalize.map_values`

当需要对 `mapping` 的 values 做多步整形时使用(按顺序执行 steps):

```yaml
normalize:
  map_values:
    steps:
      - take_first:
          on_empty: miss
      - project_fields:
          on_missing: error
          fields:
            order_id: {from_key: true}
            review_status: {extract: review_status}
```

## 受控扩展点 `normalize.call_by`

用于覆盖 declarative normalize 难以表达的场景,但保持可审计与可诊断:

- 引用解析与 `loader` 相同(支持相对引用,受 allowlist 约束)
- 固定 contract: whole-result `Mapping -> Mapping`

```yaml
normalize:
  call_by: myapp.normalizes:normalize_source_x
  map_values:
    steps: [...]
```

建议签名:
- `fn(result, ctx) -> Mapping`
  - `ctx.source_id`
  - `ctx.kind`
  - `ctx.config_path`

## Migration Checklist

1) 识别 wrapper 形状:
   - `mapping[key -> list[row]]` → 优先用 `take_first`/`map_values`
   - `mapping[key -> nested_dict]` → 优先用 `project_fields`
2) 若业务存在 int/enum key 的 nested dict,用 bracket path 表达(例如 `"[1].x"`)
3) 只有在 declarative normalize 无法表达且不想引入 wrapper module 时,再使用 `normalize.call_by`
