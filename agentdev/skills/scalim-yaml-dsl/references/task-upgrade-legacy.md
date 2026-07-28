# Upgrade Legacy YAML

## 何时读取

- 用户明确说“升级旧 YAML DSL”
- `validate` / `schema validate` 提示 legacy field
- 你看到旧版 `bind` / `to_bind`、旧顶层结构、旧输出字段写法

## 原则

- 直接升级到当前写法
- 不保留兼容层
- 升级后立刻跑 `schema validate` 与 `validate`

## 如何定位需要看的升级批次

1) 先跑 `schema validate` 与 `validate`(默认 strict unknown fields),取第一条错误的 `path + message`
2) 优先读生成的 upgrades 摘要: `references/generated/yaml-dsl-upgrades.gen.md`
3) 再按摘要里的路径打开对应批次的完整升级文档(`references/upgrades/*.md`)

### 错误症状 → 优先打开的批次(快速路径)

| 症状 / 关键词 | 打开 |
|---|---|
| `write_defaults was removed` / YAML `resources.books.*.write_defaults` | `references/upgrades/2026-07-12-book-write-policy-python-ssot.md` |
| `xlsx_memory.budget was removed` / YAML book `budget` | 同上 |
| `xlsx_file was removed` / `xlsx_memory was removed` / `xlsx_memory with export_xlsx was removed` | `references/upgrades/2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md` |
| `BookWriteDefaultsOverride` / `BookBudgetOverride` / write·budget overlay | `references/upgrades/2026-07-12-book-write-policy-python-ssot.md` |
| `max_groups was removed` / `max_distinct was removed` / `distinct_on_overflow was removed` / cardinality guardrails | `references/upgrades/2026-07-24-remove-derived-outputs-cardinality-guardrails.md` |
| `has removed 'score_by_rank'` / `score_by_rank` → `compute` | `references/upgrades/2026-07-24-remove-score-by-rank-builtin.md` |
| `workflow.options` / `cache_pool` in YAML / `share_preload_cache` | 查 upgrades 摘要里 runtime-policy / workflow 相关批次；**不要**照抄 `2026-03-18` 里已过时的 `workflow.options.ctx` / `sheetbooks` 写法 |
| `sheetbooks` / `workbooks` / `writes:` (旧 workflow 字段) | 先读 `2026-03-18` 理解历史，再以当前 `resources.books` + `2026-07-12` policy 为准 |

说明: AUTOGEN 索引按时间列出全部批次；**当前权威**以 SKILL 硬规则 + 最新相关 upgrade 为准，旧批次仅作迁移上下文。

## YAML DSL 升级批次索引 (自动生成)

<!-- BEGIN AUTOGEN:yaml-dsl-upgrades -->
- 2026-03-10: yaml-field-extract
  - SSOT: `references/upgrades/2026-03-10-yaml-field-extract.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-10-yaml-field-extract/`
  - Spec: `llmanspec/specs/yaml-field-extract/spec.md`
- 2026-03-10: yaml-source-normalize
  - SSOT: `references/upgrades/2026-03-10-yaml-source-normalize.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-10-yaml-source-normalize/`
  - Spec: `llmanspec/specs/demand-dsl/spec.md`
- 2026-03-11: yaml-params-template
  - SSOT: `references/upgrades/2026-03-11-yaml-params-template.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
  - Spec: `llmanspec/specs/demand-dsl/spec.md`
- 2026-03-13: demand-dsl-breaking
  - SSOT: `references/upgrades/2026-03-13-demand-dsl-breaking.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-12-yaml-dsl-micro-tunes/`
  - Spec: `llmanspec/specs/demand-dsl/spec.md`
- 2026-03-13: derived-outputs-set-aggregations
  - SSOT: `references/upgrades/2026-03-13-derived-outputs-set-aggregations.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-13-derived-outputs-set-aggregations/`
  - Spec: `llmanspec/specs/execution-derived-outputs/spec.md`
- 2026-03-13: yaml-dsl-outputs
  - SSOT: `references/upgrades/2026-03-13-yaml-dsl-outputs.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-13-yaml-dsl-outputs/`
  - Spec: `llmanspec/specs/yaml-dsl-schema/spec.md`
- 2026-03-13: yaml-reuse-workflow
  - SSOT: `references/upgrades/2026-03-13-yaml-reuse-workflow.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-13-yaml-dsl-imports/`
  - Spec: `llmanspec/specs/yaml-dsl-imports/spec.md`
- 2026-03-13: yaml-source-normalize-shapes
  - SSOT: `references/upgrades/2026-03-13-yaml-source-normalize-shapes.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-12-yaml-source-normalize-shapes/`
  - Spec: `llmanspec/specs/yaml-source-normalize/spec.md`
- 2026-03-14: yaml-dsl-output-fields-alias
  - SSOT: `references/upgrades/2026-03-14-yaml-dsl-output-fields-alias.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-14-yaml-dsl-output-fields-alias/`
  - Spec: `llmanspec/specs/yaml-dsl-schema/spec.md`
- 2026-03-16: yaml-dsl-outputs-aggregate-fields
  - SSOT: `references/upgrades/2026-03-16-yaml-dsl-outputs-aggregate-fields.md`
  - llmanspec: `llmanspec/changes/yaml-dsl-outputs-aggregate-fields-simplify/`
- 2026-03-18: yaml-workflow-dag-ctx-resources
  - SSOT: `references/upgrades/2026-03-18-yaml-workflow-dag-ctx-resources.md`
  - llmanspec: `llmanspec/changes/archive/2026-03-18-c20-workflow-dag-context-passing/`
  - Spec: `llmanspec/specs/yaml-dsl-workflow/spec.md`
- 2026-04-07: yaml-dsl-import-roots-registry
  - SSOT: `references/upgrades/2026-04-07-yaml-dsl-import-roots-registry.md`
  - llmanspec: `llmanspec/changes/archive/2026-04-07-c41-yaml-dsl-import-roots-registry/`
  - Spec: `llmanspec/specs/yaml-dsl-project-config-schema/spec.md`
- 2026-04-08: yaml-dsl-api-naming-alignment
  - SSOT: `references/upgrades/2026-04-08-yaml-dsl-api-naming-alignment.md`
  - llmanspec: `llmanspec/changes/archive/2026-04-07-c1-yaml-dsl-api-naming-alignment/`
- 2026-07-12: book-write-policy-python-ssot
  - SSOT: `references/upgrades/2026-07-12-book-write-policy-python-ssot.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-12-c20-book-write-policy-python-ssot/`
  - Spec: `llmanspec/specs/yaml-dsl-books-resources/spec.toon`
- 2026-07-13: normalize-xlsx-book-ir-path-presence
  - SSOT: `references/upgrades/2026-07-13-normalize-xlsx-book-ir-path-presence.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-13-c25-normalize-xlsx-book-ir-path-presence/`
- 2026-07-13: unified-xlsx-book-kind
  - SSOT: `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-13-c20-add-unified-xlsx-book-kind/`
- 2026-07-18 — `ISink.discard` 显式失败清理合约
  - SSOT: `references/upgrades/2026-07-18-sink-discard-explicit-contract.md`
- 2026-07-18 — tabular bus object + sink accept / opt-in precheck
  - SSOT: `references/upgrades/2026-07-18-tabular-bus-object-sink-accept-precheck.md`
- 2026-07-20: remove-deprecated-xlsx-file-memory-kinds
  - SSOT: `references/upgrades/2026-07-20-remove-deprecated-xlsx-file-memory-kinds.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds/`
- 2026-07-24: remove-derived-outputs-cardinality-guardrails
  - SSOT: `references/upgrades/2026-07-24-remove-derived-outputs-cardinality-guardrails.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-24-c15-remove-derived-outputs-cardinality-guardrails/`
- 2026-07-24: remove-score-by-rank-builtin
  - SSOT: `references/upgrades/2026-07-24-remove-score-by-rank-builtin.md`
  - llmanspec: `llmanspec/changes/archive/2026-07-24-c0-remove-score-by-rank-builtin/`
<!-- END AUTOGEN:yaml-dsl-upgrades -->

## whole-result reshape: 用 `normalize`,不用字段级 `extract`

如果你的 lookup loader 返回 `list[row]`,而你过去通过 Python wrapper 把它改成 `key -> row` mapping,现在可以优先用 `sources.<id>.normalize.index_by_key` 完成归一化.

边界:
- `normalize`: 对整个 source 返回值做一次 reshape(发生在字段读取前)
- `extract`: 从单条 row value 里取字段(包含 nested 取值与 rename)

## 必查项目

### 1. legacy 字段

以下字段不再允许出现在当前结构:

- `relations_sql_like`
- `relations_graph`
- `foreign_key`
- `target`
- `from`
- `via`
- `column`
- `pk`
- `pk_transform`
- `derived`
- `key_transform`
- `primary`
- `resources.books.*.write_defaults`(迁到 Python `BookWritePolicy` / `resources_policy`;见 `2026-07-12-book-write-policy-python-ssot.md`)
- `resources.books.*.xlsx_memory.budget`(迁到 Python `BookBudgetPolicy`;同上)
- `workflow.options.*`(runtime policy boundary;不要写回 YAML)

### 2. 顶层 `fields`

- 顶层 `fields` 只允许派生字段
- 如果顶层字段里出现源字段写法(例如 `extract:`/`relation:`/`value_cast:`),说明位置错,需要移到 `main_source.fields` 或 `sources.<id>.fields`

### 3. 源字段取值: `field` → `extract` (breaking)

旧写法(不再允许):

```yaml
main_source:
  fields:
    customer_id:
      field: customer_id_col
```

新写法:

```yaml
main_source:
  fields:
    customer_id:
      extract: customer_id_col
```

提示:

- `fields.*.field` 已从稳定 YAML authoring surface 移除,出现即 fail-fast
- `extract` 省略时,等价于 `extract: <field_id>`(顶层同名 key)

### 4. `bind` / `to_bind` -> `params` 模板指令(`$keys` / `$rows`)

旧写法(不再允许,会 fail-fast):

```yaml
bind:
  use_keys:
    param: ids
```

新写法(推荐):

```yaml
params:
  ids: {$keys: {as: set}}
```

`rows` 模式:

```yaml
params:
  rows: {$rows: {cache_mode: batch}}
```

提示:

- `$rows` 会触发 rows barrier.在 `parallel_mode="adaptive"` 下,该层 LoadRef 会按串行执行.
- `cache_mode: preload_forever` 的 source 禁止在 `params` 中使用 `$keys/$rows`.

### 5. 顶层 `output` → `outputs`

旧写法:

```yaml
output:
  format: csv
  path: ./output/report.csv
  fields:
    - order_id
    - customer_name
```

新写法:

```yaml
resources:
  files:
    report:
      kind: csv_file
      path: ./output

outputs:
  - name: detail
    to: {file: report}
    fields: [order_id, customer_name]
```

说明:

- `output:` 顶层字段已移除(不再支持兼容层);必须升级为 `outputs:`(有序列表)
- `resources.*.path` 语义为输出 root 目录(版本化输出 D-2);产物通过稳定 facade 定位(例如 `scalim.shortcuts.resources.outputs`),或显式指定版本目录定位
- `outputs.*.fields` 推荐优先用 `field_id` 字符串列表;允许的结构以当前 schema 为准(需要时查 CLI `scalim-cli yaml-dsl schema show` 与 `references/syntax-catalog.gen.md`)

### 6. relation 引用

- `relation` 支持 string ref/alias/内联 `steps`:
  - `relation: <relation_id>` 引用 `relations.<relation_id>`
  - `relation: *anchor` (YAML alias)
  - `relation: {steps: [...]}` (内联)
- 推荐优先用 string ref(可读性更好;也更方便从 alias 迁移)

### 7. step 字段选择

- `steps.from` / `steps.to` 使用 `source.field_id`(或 list)
- 即使 loader 真实列名不同,这里仍然写 YAML 的 `field_id`

## 升级顺序

1. 清掉 legacy 字段
2. 规范化 `main_source` / `sources` / 顶层 `fields`
3. 把 `fields.*.field` 全部升级为 `fields.*.extract`
4. 把所有 `bind` / `to_bind` 改成 `params` 模板中的 `$keys` / `$rows` 指令节点
5. 把 `output:` 顶层字段升级为 `outputs:`
6. 检查 relation steps 是否还在写 `data_key`
7. 跑校验并修掉剩余错误

## 最小自检

```bash
uv run scalim-cli yaml-dsl schema validate <file.yaml>
uv run scalim-cli yaml-dsl validate <file.yaml>
```

## 常见报错到修复动作

- `Legacy field 'xxx' is not allowed`
  - 删除旧字段,改写到当前入口结构
- `Derived field 'xxx' must declare compute/call_by`
  - 如果它是源字段,请移回 `main_source.fields`/`sources.*.fields`;如果它是派生字段,请补 `compute` 或 `call_by`
- `Legacy YAML syntax is not supported: top-level 'output'. ...`
  - 顶层 `output:` 已移除;按本页第 5 节升级为 `outputs:` + `resources.files` + `outputs.*.to.file`
- `Legacy \`$runtime.<name>\` placeholder is not supported; use \`{$init_var: <name>}\``
  - 把所有 `$runtime.xxx` 全量替换为 `{$init_var: xxx}`
- `Field 'xxx' is defined multiple times; field_id must be unique ...`
  - 先在 `main_source.fields/sources.*.fields/fields` 中把重名 `field_id` 重命名,再在 `outputs.*.fields` 引用新 `field_id`
- `Unknown field`
  - 先查 typo,再查是否仍在使用旧字段名

需要完整字段与 schema 细节时再读:

- [syntax-catalog.gen.md](syntax-catalog.gen.md)
