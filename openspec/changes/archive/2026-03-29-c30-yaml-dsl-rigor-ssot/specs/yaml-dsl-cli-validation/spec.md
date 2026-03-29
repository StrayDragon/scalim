## ADDED Requirements

### Requirement: CLI validation MUST reuse the unified YAML load facade

系统 MUST 要求 `scalim-cli yaml-dsl validate`（或等价 CLI 校验入口）复用统一的 YAML load facade,以保证与 runtime/compile/workflow validate 的一致性.

#### Scenario: CLI validate matches compile error structure
- **WHEN** 某份 YAML 在 runtime compile/run 中因 parse/duplicate key 失败
- **THEN** 同一份 YAML 在 CLI validate 下 MUST 以相同 ErrorEnvelope 结构失败（差异仅限入口标识/命令上下文）

