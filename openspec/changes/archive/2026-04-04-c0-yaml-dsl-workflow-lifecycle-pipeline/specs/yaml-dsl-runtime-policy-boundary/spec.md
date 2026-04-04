# yaml-dsl-runtime-policy-boundary Specification

## ADDED Requirements

### Requirement: demand parsing MUST be parser-only; runtime-only diagnostics MUST run only at policy-aware boundaries
系统 MUST 将 demand 的“解析/结构化”与“runtime-only diagnostics/compile”彻底分离：

- demand YAML 的 parse/loader API MUST 为 parser-only（只负责解析与结构抽取）
- parser-only 路径 MUST NOT 运行任何依赖 effective runtime policy 的 diagnostics（例如 `validate_unique_field_names`）
- runtime-only diagnostics MUST 仅在具备 effective runtime policy 的边界运行（例如 workflow preflight 或 demand runtime compile）

#### Scenario: parser-only demand load does not fail on duplicate display names
- **GIVEN** 某个 demand fields 存在 duplicate effective field display names
- **WHEN** 系统仅执行 parser-only 的解析/结构预加载
- **THEN** 解析/预加载 MUST 成功返回结构信息
- **AND** MUST NOT 因 `validate_unique_field_names` 直接失败

### Requirement: parser-only demand loader MUST NOT expose runtime-only diagnostics knobs
为减少误用面并从结构上约束边界，系统提供的 parser-only demand loader MUST NOT 暴露任何“启用/禁用 runtime-only diagnostics”的参数（例如 `validate_unique_field_names` 这类开关）；runtime-only diagnostics 必须只能通过 policy-aware 边界的 typed runtime policy 输入控制。

#### Scenario: parser-only loader cannot be called with validate_unique_field_names
- **WHEN** 调用方尝试以 `validate_unique_field_names=...` 调用 parser-only demand loader
- **THEN** 该调用 MUST 不可用（例如参数不存在或直接报错）
