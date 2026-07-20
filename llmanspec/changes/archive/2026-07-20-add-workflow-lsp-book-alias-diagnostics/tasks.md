## 1. Spec

- [x] 修改 `yaml-dsl-lsp-server` r564：允许 books 静态迁移诊断；禁止 runtime compile/run
- [x] 增加 scenario：workflow `xlsx_file`/`xlsx_memory` → diagnostics 含迁移文案
- [x] `llman sdd validate add-workflow-lsp-book-alias-diagnostics --strict`

## 2. Implement

- [x] `_collect_workflow_diagnostics` 增加 books 静态迁移诊断（path 前缀 `workflow.`）
- [x] 同 path 已有迁移错误时抑制 unknown-field 重复

## 3. Tests / contracts

- [x] 更新 `workflow_books_removed_alias_diagnostics` snapshot + 断言含 `xlsx_file was removed`
- [x] editor-semantics：workflow 旧别名 MUST 含迁移文案；合法 `xlsx` 仍干净
- [x] `uv run pytest tests/yaml_dsl/test_yaml_dsl_lsp_contract_suite.py tests/yaml_dsl/test_yaml_dsl_editor_semantics.py -q`

## 4. Gate

- [x] `just qa`
