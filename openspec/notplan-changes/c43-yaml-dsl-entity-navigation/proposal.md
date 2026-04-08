## Why

YAML DSL 文件内部存在大量实体 ID 引用：`fields.*.source` 引用 `sources` 下的 key、`relations.*.steps[*].from/to` 引用 `source_id.field_id`、workflow 的 `depends_on` 引用 run 节点。这些是用户**最频繁**的导航目标——比 Python 引用跳转更常用。

当前这些 ID 引用只是普通字符串，编辑器无法跳转、无法补全、无法 hover 查看摘要。用户需要手动在文件内滚动查找对应的定义位置，体验割裂。

本提案聚焦：**让 YAML DSL 内部实体 ID 引用具备 definition / completion / hover 能力**，使 DSL 像"有符号系统的语言"一样可导航。

## Goals

- **G1：Go to Definition**：在 ID 引用位置 F12 可跳转到对应实体的声明点。
- **G2：Completion**：在 ID 引用位置补全可用实体 ID，含 snippet。
- **G3：Hover**：悬停在 ID 上显示被引用实体的摘要信息。
- **G4：Document Symbols**：提供 YAML DSL 结构大纲（可折叠、可跳转）。

## Non-Goals

- 不做 rename / find references / refactor（超出本提案范围，可作为后续演进）。
- 不跨文件引用（只处理同一 YAML 文件内的实体引用）。
- 不处理 Python 引用 / builtin callable / imports alias（分别由现有能力和 c42 负责）。
- 不引入 workspace-wide 索引（保持单文件解析）。

## Proposal

### 1) Go to Definition（YAML 实体 ID 引用）

#### Reference Forms（引用位置 → 目标）

| 引用位置 | 引用值 | 跳转目标 |
|---|---|---|
| `fields.*.source` | `<source_id>` | `sources.<source_id>` 的 key 位置 |
| `fields.*.relation` | `<relation_id>` | `relations.<relation_id>` 的 key 位置 |
| `relations.*.steps[*].from` | `<source_id>.<field_id>` | `sources.<source_id>` key 位置（首选）或 `fields.<field_id>` key 位置 |
| `relations.*.steps[*].to` | `<source_id>.<field_id>` | 同上 |
| `outputs[*].from` | `<output_id>`（如语义存在） | 对应 output 定义点 |
| workflow `depends_on` | `<run_id>` | 对应 run 节点定义点 |
| workflow `main_rows_from.run` | `<run_id>` | 同上 |

#### Expected Behavior

1) 光标在 `<source_id>` 上 → 跳到 `sources:` 下对应 key 的行。
2) 光标在 `<source_id>.<field_id>` 的 `<source_id>` 部分 → 跳到 sources 定义。
3) 光标在 `<source_id>.<field_id>` 的 `<field_id>` 部分 → 跳到 fields 定义（如果 field_id 可解析到唯一 field）。
4) 目标不存在 → 返回空 + Diagnostic（severity: hint）提示 "Unknown source/relation: <id>"。

实现约束（Range 精度）：
- 对 `source_id.field_id` 这类复合引用，cursor extraction 必须能在同一 scalar string 内返回子 token 的精确 range（否则无法正确区分 source/field 的 definition 目标）。

#### 前置依赖

依赖 c40 的多 Location 返回框架和 Resolution Trace。

### 2) Completion（实体 ID 补全）

#### Trigger Points

| 位置 | 触发条件 | 补全内容 |
|---|---|---|
| `fields.*.source:` | value 位置 | 已声明的 `sources` keys |
| `fields.*.relation:` | value 位置 | 已声明的 `relations` keys |
| `relations.*.steps[*].from:` / `to:` | value 位置，`<source_id>.` 之后 | 该 source 下已声明的 field ids |
| `relations.*.steps[*].from:` / `to:` | value 位置，输入起始 | 已声明的 `sources` keys + `.` 后触发 field 补全 |
| workflow run 引用位置 | value 位置 | 已声明的 run ids |

#### Expected Behavior

1) 列出当前文件中已声明的实体 ID（仅限已解析到的 keys）。
2) 每项显示简短标签（例如 source 补全显示 `source_id (loader: ...)` ）。
3) 对 `from/to` 位置提供 snippet：`${1:source_id}.${2:field_id}`。
4) 不补全未声明的 ID（不提供"创建"建议）。

### 3) Hover（实体摘要）

#### Trigger

悬停在 `source_id` / `relation_id` / `run_id` 等引用值上。

#### Expected Behavior

显示被引用实体的摘要卡片：

- **Source**：`source_id`、loader 类型、key 字段、字段数量。
- **Relation**：`relation_id`、steps 数量、涉及的 sources。
- **Workflow Run**：`run_id`、depends_on 列表（如有）。

信息来源：对当前文件 YAML 解析结果做只读摘要，不执行任何 Python。

### 4) Document Symbols / Outline

#### Expected Behavior

1) `textDocument/documentSymbol` 返回 YAML DSL 的结构大纲：

```
📄 demand.yaml
├── 📦 sources
│   ├── src_a
│   └── src_b
├── 📋 fields
│   ├── field_x
│   └── field_y
├── 🔗 relations
│   └── rel_1
└── 📤 outputs
    └── out_1
```

2) 点击符号可跳转到对应位置。
3) 支持 VSCode 的 Outline 视图和 breadcrumbs。

#### 实现要点

- 解析 YAML 顶层 keys（`sources` / `fields` / `relations` / `outputs` / `workflows`）及其子 keys。
- 对 workflow 类型，额外包含 run 节点层级。
- SymbolKind 使用 `Class`（顶层分组）、`Field`（实体 ID）等近似映射。

## Options & Trade-offs

### 1) 单文件 vs 跨文件引用

- **单文件（推荐）**：只解析当前 YAML 文件内的实体。实现简单、可靠、无 IO 负担。
- **跨文件**：需要读取 `$import` 的 fragment 文件来解析跨文件 ID。收益大但复杂度高（fragment 可能有循环依赖、IO 成本、缓存一致性）。
- 结论：本提案只做单文件；跨文件作为后续演进。

### 2) 实体解析策略

- **YAML 结构解析（推荐）**：直接解析 YAML AST 提取 keys。准确、不依赖 schema。
- **JSON Schema 驱动**：根据 schema 约束推断哪些字段是 ID 引用。更通用但依赖 schema 完整性。
- 结论：本提案使用 YAML 结构解析 + 硬编码引用位置映射（与 Reference Forms 表一致）。

### 3) Document Symbols 的粒度

- **两层（推荐）**：顶层分组 + 实体 ID。简洁、满足 80% 导航需求。
- **深层嵌套**：展开 relation steps、workflow DAG 等。信息更丰富但增加解析复杂度。
- 结论：先用两层，后续按需加深。

## Validation（fixture 覆盖）

- **Go to Definition**：
  - `fields.*.source: src_a` → 跳到 `sources.src_a`。
  - `from: src_a.field_x` → 光标在 `src_a` 跳 sources，在 `field_x` 跳 fields。
  - 引用不存在的 ID → 返回空 + diagnostic。
- **Completion**：
  - `source:` 位置 → 列出所有 `sources` keys。
  - `from: src_a.` → 列出 src_a 下的 field ids。
  - 无已声明实体 → 补全列表为空（不报错）。
- **Hover**：
  - 悬停在有效 source_id → 显示摘要卡片。
  - 悬停在无效 ID → 不触发 hover（或显示"Unknown entity"）。
- **Document Symbols**：
  - 返回正确的层级结构。
  - 无 sources/fields 的文件 → 返回空 symbols。

## Impact（涉及模块）

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
  - 新增 YAML 实体解析模块（引用位置映射表 + ID 解析逻辑）
- server：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
  - 注册 `textDocument/definition`、`textDocument/completion`、`textDocument/hover`、`textDocument/documentSymbol` handler
- specs（后续转正时）：
  - `openspec/specs/yaml-dsl-lsp-server/spec.md`（扩展 entity navigation 部分）
