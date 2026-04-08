## Why

YAML DSL 的 `compute`/`where` 等安全表达式里，大量使用“字段 ID 作为变量名”（例如 `compute: "a + b"`、`where: "no_promotion"`）。目前这些表达式在编辑器里只是普通字符串：无法补全可用字段、无法跳转到字段定义、hover 也看不到字段摘要与上下文，导致写错/拼写错误/作用域不匹配时排障成本高，且很难理解某个表达式在当前上下文到底允许引用哪些字段。

## What Changes

- 为安全表达式中的字段引用提供 editor 语义（completion/hover/definition）：
  - completion：在 `compute`/`where` 等表达式字符串内，基于当前位置的作用域列出可用字段 ID 候选。
  - go-to-definition：光标位于表达式里的某个字段标识符时，跳转到同一 YAML 文件内该字段的声明点（源字段或派生字段）。
  - hover：显示字段摘要（`name`、producer/来源、以及该字段在本文件中的声明片段摘要），用于快速理解上下文。
- 作用域必须可解释且尽量贴近运行时语义：
  - `fields.*.compute`：可引用本 demand 文件中可解析且不歧义的字段 ID（含源字段与派生字段）。
  - `outputs[*].where`：可引用该输出行上下文允许的字段集合（至少与运行时校验口径一致）。
  - `outputs[*].aggregate.fields.*.compute`：仅允许引用 `group_by` + `aggregate.fields` 中声明的 out_field_id（含派生字段）。
- 全程保持静态无副作用：
  - 不执行用户代码；不运行 demand/workflow；仅做 YAML 结构解析与安全表达式 AST 解析/依赖提取。
  - 解析失败必须降级为“空结果 + 可诊断信息”，不得 crash。

## Capabilities

### New Capabilities

<!-- 本变更优先扩展既有 LSP/semantics core 能力；不新增 capability spec。 -->

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: 增加“表达式内字段引用”的光标抽取与解析能力，并提供字段索引/作用域信息以支撑 hover/definition/completion。
- `yaml-dsl-lsp-server`: 在 `compute`/`where` 等表达式字符串内支持 completion/hover/definition，并保证与运行时字段依赖/作用域约束一致。

## Impact

- shared core（editor semantics）：
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`：表达式字段引用解析、字段索引与作用域计算（复用 `scalim` 现有依赖提取/校验语义）。
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py`：扩展光标抽取，能定位到表达式内部的字段 token 与 range。
- LSP server：
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`：把新的抽取与解析能力接入 `textDocument/definition`、`textDocument/hover`、`textDocument/completion`。
