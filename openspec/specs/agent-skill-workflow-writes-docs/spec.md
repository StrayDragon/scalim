# agent-skill-workflow-writes-docs Specification

## Purpose
定义并约束 `scalim-yaml-dsl` skill 的 workflow YAML 语法索引生成规则,确保生成物的关键 key paths 与 canonical workflow schema 一致,避免文档漂移误导作者与工具链.
## Requirements
### Requirement: Generated syntax catalog MUST reflect workflow schema key paths (`books`, not legacy resource groups)
系统 MUST 保证 `scalim-yaml-dsl` skill 的生成语法目录在 workflow YAML 部分输出的 key paths 与 canonical workflow schema 一致:

- MUST 包含 `workflow.resources.books`
- MUST NOT 输出任何已移除的 workflow IO authoring surface(legacy resource groups / workflow 写入 intents 等)

#### Scenario: syntax-catalog key paths match workflow schema
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow “Key Paths” MUST 包含 `workflow.resources.books`
- **AND** MUST NOT 包含任何已移除的 workflow IO authoring surface
