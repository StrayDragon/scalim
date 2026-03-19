## ADDED Requirements

### Requirement: by_yaml runtime accepts template_vars for YAML precompile
系统 SHALL 扩展 by_yaml runtime 的对外入口 `run/compile` 与 `RunOptions`,允许调用方提供可选的 `template_vars: Mapping[str, object]`,用于在 YAML parse 前执行 LiteJinja2 文本预编译.

当调用方未提供 `template_vars` 时,adapter MUST 不启用模板渲染步骤,并保持既有 YAML parse/校验/编译语义.

#### Scenario: compile receives template_vars and precompiles YAML
- **GIVEN** YAML 文本包含 LiteJinja2 模板语法 `{{ ... }}`
- **WHEN** 调用方执行 `compile(..., template_vars={...})`
- **THEN** adapter MUST 在 YAML parse 前完成预编译
- **AND** 后续编译链路(validator/`DemandConfig -> DemandIr`) MUST 基于预编译后的配置继续执行

