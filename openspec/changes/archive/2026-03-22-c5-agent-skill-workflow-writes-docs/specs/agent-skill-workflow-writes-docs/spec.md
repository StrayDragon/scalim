## ADDED Requirements

### Requirement: Generated syntax catalog MUST reflect workflow schema key paths (`writes`, not `write_to`)
系统 MUST 保证 `scalim-yaml-dsl` skill 的生成语法目录在 workflow YAML 部分输出的 key paths 与 canonical workflow schema 一致:

- MUST 包含 `workflow.runs[*].writes`
- MUST NOT 输出 `workflow.runs[*].write_to`

#### Scenario: syntax-catalog key paths match workflow schema
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow “Key Paths” MUST 包含 `workflow.runs[*].writes`
- **AND** MUST NOT 包含 `workflow.runs[*].write_to`

