## Context

- LSP 现状:
  - 已支持 YAML DSL 文档识别与 diagnostics 发布。
  - 已支持 Python 引用与 `$import` 引用的 cursor extraction + hover/definition/completion（局部）。
  - 但 YAML DSL **文件内部**大量使用实体 ID 字符串（sources/fields/relations/workflow runs 等），目前仍是“纯字符串”，缺少导航与补全。
- 现有解析工具可复用:
  - `scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load.build_yaml_location_index` 可将 YAML 逻辑路径映射到 `(line, col)`。
  - LSP 侧已有基于 `ruamel.yaml` compose 的 cursor extraction 框架，可精准拿到 scalar bounds。

约束/护栏:
- 本变更只处理**同一文件内**实体引用（无跨文件索引）。
- 全程静态无副作用；解析失败必须降级为空结果，不 crash。
- Range 精度必须覆盖 `source_id.field_id` 的子 token（点到哪跳到哪）。

## Goals / Non-Goals

**Goals:**
- definition：在实体 ID 引用位置 F12 跳转到声明点。
- completion：在实体 ID 引用位置补全可用 ID（含 snippet）。
- hover：悬停展示被引用实体的摘要信息。

**Non-Goals:**
- 不做 rename / find references / refactor。
- 不跨文件引用（fragment 展开与跨文件定位由 `yaml-dsl-editor-effective-expansion` 处理）。
- 不处理 builtin callable / imports alias / preset（由 `yaml-dsl-lsp-sugar-support` 处理）。
- 不实现 `textDocument/documentSymbol`（由 YAML language server/extension 提供通用 YAML symbols，本变更不重复实现）。
- 不做 workspace-wide 全量索引。

## Decisions

### 1) 单文件 `EntityIndex`（解析一次，多处复用）

- 在 server 的 `_DocumentState` 中缓存一个只读索引（按 `uri` + 文档版本更新）:
  - `YamlLocationIndex`（YAML path → line/col）
  - `EntityIndex`（实体声明与摘要）
- `EntityIndex` 至少包含:
  - sources: `source_id -> (key_range, summary)`
  - fields:
    - derived fields: `field_id -> (key_range, summary)`
    - per-source fields: `(source_id, field_id) -> (key_range, summary)`
  - relations: `relation_id -> (key_range, summary)`
  - workflow runs（若为 workflow DSL）: `run_id -> (key_range, summary)`

实现选择:
- 位置索引优先用 `build_yaml_location_index`（逻辑路径稳定、易测试）。
- 摘要信息优先用“安全的 mapping 读取”（不执行 Python），只取少量字段（loader/steps 数量等）。

### 2) Cursor extraction: 增量扩展（复用既有框架）

- 在 `cursor_extraction.py` 增加 `extract_yaml_dsl_entity_reference_by_cursor(...)`:
  - 通过 YAML compose node 遍历获得 `yaml_path` 与 scalar bounds
  - 基于 `yaml_path` 判定当前是否处于“实体引用字段”:
    - `fields.*.source`
    - `fields.*.relation`
    - `relations.*.steps.*.from` / `.to`
    - workflow `depends_on` / `main_rows_from.run` 等
- 对复合引用 `source_id.field_id`:
  - 在 scalar 文本内用光标列位置做子 token 拆分
  - 返回精确的 `EditorRange`（仅覆盖被选中的子 token）

### 3) Definition: “引用种类 → 索引查找 → location”

- definition handler 的策略:
  - 根据 extraction 结果确定目标实体类型
  - 在 `EntityIndex` 中查找声明点 range
  - 找不到则返回空（可在 hover/diagnostics 提示 Unknown ID）
- 对 `source_id.field_id`:
  - 光标在 `source_id` 段 → 跳 sources key
  - 光标在 `field_id` 段 → 跳 fields key（需可解析到唯一 field）

### 4) Completion: 只补全已声明 ID（稳定排序）

- completion 触发点按 `yaml_path`:
  - `fields.*.source` → sources keys
  - `fields.*.relation` → relations keys
  - `relations.*.steps.*.from/to`:
    - 起始位置：sources keys + snippet `${1:source}.${2:field}`
    - `source_id.` 之后：该 source 的 field ids
  - workflow 引用位置：run ids
- 排序:
  - 默认字母序（稳定）
  - 可选：在 detail/description 显示摘要（例如 loader 类型）

### 5) Hover: “摘要卡片”最小集

- hover 内容严格限量（避免噪声与性能问题）:
  - Source: `source_id`、loader 类型、fields 数量
  - Relation: `relation_id`、steps 数量、涉及的 sources
  - Workflow Run: `run_id`、depends_on 列表（若存在）

### 6) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
- 禁止手改:
  - 任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
- Drift gates:
  - `just qa`
  - `just openspec-check`

## Risks / Trade-offs

- [YAML parse 失败/重复键] → 统一降级为空索引 + warnings；diagnostics 仍由既有校验流程负责。
- [复合 token range 不精确] → 为 `source_id.field_id` 建 fixture，覆盖“点在左/右/点号附近”的行为。
- [实体 ID 歧义（同名字段）] → definition 返回多候选（依赖 `yaml-dsl-lsp-resolution-infra` 的多 location/排序框架）或在 hover 提示需要字符串 disambiguate。
