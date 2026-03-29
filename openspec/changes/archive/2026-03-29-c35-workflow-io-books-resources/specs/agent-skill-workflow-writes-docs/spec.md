## MODIFIED Requirements

### Requirement: Generated syntax catalog MUST reflect workflow schema key paths (`books`, not legacy resource groups)
系统 MUST 保证 `scalim-yaml-dsl` skill 的生成语法目录在 workflow YAML 部分输出的 key paths 与 canonical workflow schema 一致:

- MUST 包含 `workflow.resources.books`
- MUST NOT 输出 `workflow.resources.workbooks` / `workflow.resources.csvs` / `workflow.resources.sheetbooks`
- MUST NOT 输出 `workflow.runs[*].writes`

#### Scenario: syntax-catalog key paths match workflow schema
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow “Key Paths” MUST 包含 `workflow.resources.books`
- **AND** MUST NOT 包含 legacy resource groups 或 `writes`
