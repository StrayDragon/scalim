<!--
本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.
Sources:
- artifacts/skills/scalim-yaml-dsl/references/upgrades/2026-03-13-demand-dsl-breaking.md
-->
# 2026-03-13: demand-dsl-breaking

## 变更摘要

本批次聚焦 YAML DSL 的几处语法收敛与可用性改良:

- `relation` 支持 string ref: `relation: <relation_id>` 引用 `relations.<relation_id>`
- `output.fields` 支持 string sugar:
  - `field_id` (例: `order_id`)
  - `source.field_id` (例: `customers.customer_name`;用于消歧;仅支持二段式)
- **BREAKING**: init vars 统一为指令节点 `{$init_var: <name>}`;旧写法 `$runtime.<name>`/`{$runtime: <name>}` 不再允许

OpenSpec 归档变更（含 proposal/design/spec/tasks）:
- `openspec/changes/archive/2026-03-12-yaml-dsl-micro-tunes/`

对应主规范(节选):
- `openspec/specs/demand-dsl/spec.md`
- `openspec/specs/yaml-dsl-schema/spec.md`
- `openspec/specs/yaml-runtime-vars/spec.md`
- `openspec/specs/source-relations/spec.md`
- `openspec/specs/yaml-dsl-micro-tunes/spec.md`

下游同步盘点:
- 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）

## Breaking: init vars 指令化

旧写法(不再允许,出现即 fail-fast):

```yaml
params:
  end_dt: "$runtime.end_dt"
```

新写法:

```yaml
params:
  end_dt: {$init_var: end_dt}
```

说明:

- `{$init_var: <name>}` 是“单键映射指令节点”,与 `$keys/$rows` 同属一类模板 AST
- 仅解析指令节点;**不做子串插值**(例如 `"and t > $init_var.end_dt"` 会被当作普通字符串透传)

## Migration Checklist

1) 全量把 `$runtime.<name>` 占位符替换为 `{$init_var: <name>}`
2) (可选) 将字段的 `relation: *anchor` 升级为 `relation: <relation_id>`
3) (可选) 将 `output.fields` 的简单场景升级为 string list sugar
