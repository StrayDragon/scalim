# c0-roadmap: YAML DSL oneOf checklist

目标: 收集 YAML DSL 中仍在使用 `kind: <variant>` 作为 discriminator 的“分支对象”,评估是否值得升级为 oneOf 分支写法:

- 旧写法: `{kind: <variant>, ...}`
- 新写法: `{<variant>: {...}}` (与 `c0-yaml-dsl-normalize-oneof` 的 `sources.*.normalize` 一致)

> 本文是“备忘/候选清单(notplan)”，不保证完整，也不承诺可落地；用于后续调研/拆分变更时的起点。

## 0. 快速定位方法(搜集更多候选)

### 0.1 Schema SSOT(优先)

查找 schema SSOT 中显式要求 `kind` 的模型:

```bash
rg -n 'SCHEMA_REQUIRED:.*\\(\"kind\"' src/scalim/dsl/yaml_dsl/schema_dsl/models
rg -n 'SCHEMA_ALL_OF' src/scalim/dsl/yaml_dsl/schema_dsl/models
```

### 0.2 严格校验/解析层(辅助)

查找 parser/validator 里对 `kind` 的 fail-fast 逻辑(通常意味着“分支对象”):

```bash
rg -n '\\.kind is required' src/scalim/dsl/yaml_dsl
rg -n 'if kind ==' src/scalim/dsl/yaml_dsl
```

### 0.3 Generated schema(结果侧验证)

确认最终 authoring surface 里暴露了哪些 `kind`:

```bash
rg -n '\"kind\"' src/scalim/dsl/yaml_dsl/schema/*.gen.json
```

## 1. 候选清单(仍是 `kind` discriminator)

### 1.1 `resources.books.*` (xlsx_file / xlsx_memory)

- [x] **已完成**（不再作为候选）: `kind` discriminator 已移除，统一为 `xlsx:` 分支写法（`anyOf: [$import | xlsx]`；`xlsx_file`/`xlsx_memory` 别名出现即 fail-fast）。由 `2026-07-13-c20-add-unified-xlsx-book-kind` / `2026-07-20-c999-remove-deprecated-xlsx-file-memory-kinds` 完成（冻结于 `freezed_changes.7z.archived`）。

> 旧草案中的“现状/可能的 oneOf 形态/注意点/触及面”已过时（`write_defaults` 也已收口 Python `BookWritePolicy`），详见冻结 change 文档，不再在本清单保留。

### 1.2 `resources.files.*` (csv_file)

- [ ] 候选: 将 `resources.files.<file_id>` 从 `kind` discriminator 升级为 oneOf 分支对象

**现状(authoring):**

```yaml
resources:
  files:
    detail_csv:
      kind: csv_file
      path: ./out
      encoding: utf-8
```

**可能的 oneOf 形态(示意):**

```yaml
resources:
  files:
    detail_csv:
      csv_file:
        path: ./out
        encoding: utf-8
```

**注意点(调研要点):**

- 当前仅一个 kind(`csv_file`)，迁移价值主要在“风格统一 + 未来扩展 kind 时更自然”，需要权衡是否值得引入 breaking change。
- demand YAML 同样存在 `$import` 语义，可参考已完成的 `resources.books.*`（`xlsx:` 分支 + `anyOf: [$import | xlsx]`）做法。

**触及面(落地时的主要改动点):**

- Schema SSOT: `src/scalim/dsl/yaml_dsl/schema_dsl/models/resources.py`（`FileConfig`），生成物 `demand.gen.json` / `workflow.gen.json`
- 解析/校验: `_internal/config_parsing/loader.py`、`validator.py`、workflow parser

## 2. 非候选 / 已经是分支风格的节点(避免重复劳动)

下面这些节点已经在 authoring surface 使用了“分支 key(oneOf)”的形态，通常不需要再从 `kind` 升级:

- `outputs[*].to`: `{file: <file_id>}` / `{book: <book_id>}` / `{sheet: <sheet_name>}`(或其组合约束)
- `outputs[*].aggregate.fields.*`: producer keys(如 `count`/`sum`/`dense_rank`/`compute`/`call_by`)已经是 `{<producer>: {...}}`
- `sources.*.normalize`: 已由 `c0-yaml-dsl-normalize-oneof` 升级为 `{index_by_key: {...}} | {take_first: {...}} | ...`

