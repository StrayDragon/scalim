## ADDED Requirements

### Requirement: workflow demand preloading MUST stay structural

workflow IR 编译阶段对 `workflow.runs[*].demand` 的预加载 MUST 仅服务于结构分析（例如 outputs/resources/dependency wiring），MUST NOT 在该阶段执行依赖 runtime diagnostics policy 的 demand 诊断。

#### Scenario: workflow IR compile accepts duplicate display names until runtime compile
- **GIVEN** 某个 workflow run 引用的 demand YAML 可以成功解析结构信息
- **AND** 该 demand 仅会在 `validate_unique_field_names=True` 时因 duplicate effective field display names 失败
- **WHEN** 系统执行 `compile_workflow_ir(...)`
- **THEN** workflow IR compile MUST 成功返回 demand-derived 结构信息
- **AND** 后续是否报 duplicate-name 错误 MUST 由 runtime demand compile 阶段决定
