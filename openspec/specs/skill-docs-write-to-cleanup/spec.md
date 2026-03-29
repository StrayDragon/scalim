# skill-docs-write-to-cleanup Specification

## Purpose
定义并约束 `scalim-yaml-dsl` skill 与相关 OpenSpec 文档对 workflow 写入字段的表述口径,确保作者不会被已移除字段 `write_to` 误导,并以 `writes` 作为唯一可用的写入 authoring surface.
## Requirements
### Requirement: Skill docs MUST not present removed workflow field `write_to` as an authoring surface
系统 MUST 保证作者面对的 skill references / OpenSpec 文档不再把 `write_to` 或 `writes` 作为当前 workflow 写入 surface；这些字段仅允许出现在“迁移/历史”说明中,并必须明确其已被移除以及替代写法为:

- `workflow.resources.books`
- demand outputs 的 `outputs_defaults.to.book` / `outputs[*].to` / `outputs[*].write`

#### Scenario: skill docs no longer advertise write_to/writes
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 不得将 `write_to` 或 `writes` 作为当前字段/路径进行描述

