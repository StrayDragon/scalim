## MODIFIED Requirements

### Requirement: Skill docs MUST not present removed workflow write fields as an authoring surface
系统 MUST 保证作者面对的 skill references / OpenSpec 文档不再把已移除的旧 workflow 写入字段作为当前 workflow 写入 surface；旧字段仅允许出现在“迁移/历史”说明中,并必须明确其已被移除以及替代写法为:

- `workflow.resources.books`
- demand outputs 的 `outputs[*].to` / `outputs[*].write` 绑定(显式 `to.book/to.sheet`)

#### Scenario: skill docs no longer advertise legacy workflow write fields
- **WHEN** 维护者运行 `just gen-agent-skill`
- **THEN** `artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 不得将已移除的旧 workflow 写入字段作为当前字段/路径进行描述

