## Context

- YAML DSL 中 `compute`/`where` 等安全表达式大量使用“字段 ID 作为变量名”（例如 `a + b`）。
- 运行时已具备:
  - 表达式依赖提取（基于 `ast.parse` 的 `Name` 收集）
  - 安全校验与求值引擎（`SecureComputeEngine`）
  - 字段定义索引（`collect_field_defs`）
- LSP 现状:
  - 表达式字符串目前只是普通 scalar，缺少 token 级别的 completion/definition/hover。

约束/护栏:
- 全程静态无副作用：不执行需求/不求值表达式。
- scope 需要“可解释且尽量贴近运行时语义”，但允许分阶段先覆盖高频场景。
- 解析失败必须降级为空结果 + 可诊断信息。

## Goals / Non-Goals

**Goals:**
- 在表达式字符串内提供字段引用语义:
  - completion：列出当前位置作用域内可用字段 ID
  - definition：跳转到同一 YAML 文件内字段声明点（必要时多候选）
  - hover：展示字段摘要与作用域信息
- 作用域覆盖:
  - `fields.*.compute`：本 demand 内可解析且不歧义的字段 ID
  - `outputs[*].where`：至少与运行时允许集合一致
  - `outputs[*].aggregate.fields.*.compute`：聚合 scope（group_by + aggregate.fields）

**Non-Goals:**
- 不做表达式 rewrite/format/rename。
- 不做跨文件字段引用解析（跨文件由 `yaml-dsl-editor-effective-expansion` 逐步打通）。

## Decisions

### 1) Cursor extraction: 表达式 token 精确定位

- 在 `cursor_extraction.py` 新增 `extract_yaml_dsl_expression_token_by_cursor(...)`:
  - 先通过 YAML compose 拿到 scalar bounds（同现有实现）
  - 再在 scalar 文本内基于光标列提取 identifier token（`[A-Za-z_][A-Za-z0-9_]*`）
  - 返回精确 `EditorRange`（只覆盖 token，而不是整个字符串）
- 仅覆盖单行 scalar（与现有 v1 cursor extraction 一致）；多行表达式后续再扩展。

### 2) Scope 计算: 复用 runtime 索引 + 最小增量逻辑

- 构建 doc 级 `ExpressionScopeIndex`（缓存于 `_DocumentState`）:
  - `FieldDefIndex`（`collect_field_defs`）
  - per-output 结构（从 raw outputs 解析得到 group_by、aggregate fields、outputs.fields 等）
- scope 规则（与 runtime 对齐的最小集合）:
  - `fields.*.compute`：所有 field_id（包含源字段与派生字段），但对同名多定义需标记为“歧义”
  - `outputs[*].where`：默认允许所有 field_id（与 runtime 常见实现一致），并在 completion 中优先排序“该 output 相关字段”（仅排序，不收窄）
  - `outputs[*].aggregate.fields.*.compute`：仅允许 `group_by` + `aggregate.fields` 声明的 out_field_id

### 3) Completion: 作用域候选 + 稳定排序

- completion items:
  - 主体为作用域内字段 ID
  - 可选附带 builtin names（由 `SecureComputeEngine.SAFE_BUILTINS` 提供，只作为提示，不作为字段）
- 排序:
  - 先“当前 output 相关字段”（若可识别）
  - 再按字母序稳定输出

### 4) Definition / Hover: “字段索引 → 摘要卡片”

- definition:
  - token 命中唯一 field_def → 跳转到字段声明 key
  - token 命中多个 field_def（歧义）→ 返回多 locations（排序/去重依赖 `yaml-dsl-lsp-resolution-infra`）
- hover:
  - 展示字段 kind（source/derived）、source_id（若有）、以及声明片段的最小摘要（例如 compute/call_by 片段存在性）
  - 同时展示“为何在该处可用”（scope explain）

### 5) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
  - （如需补复用入口）`src/scalim/dsl/yaml_dsl/_internal/config_parsing/**`
- 禁止手改:
  - 任意 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块内部
- Drift gates:
  - `just qa`
  - `just openspec-check`

## Risks / Trade-offs

- [scope 与运行时不一致] → 先以 runtime 的“允许集合”为下界（不收窄），再用排序/提示增强 authoring；必要时补 fixtures 对齐 validator 行为。
- [歧义字段名导致跳转不稳定] → 返回多候选并排序；hover 明确提示歧义与建议（用更明确的 field_id 或调整命名）。
- [表达式语法边界复杂] → v1 只做 identifier token；字符串/属性访问/下标等复杂语法后续分阶段增强。
