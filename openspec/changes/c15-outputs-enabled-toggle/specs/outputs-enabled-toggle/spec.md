## ADDED Requirements

### Requirement: demand outputs MUST support static enable/disable via `enabled`
系统 MUST 在 demand YAML 的 `outputs[*]` 上新增可选字段：

- `enabled: bool`（默认值 MUST 为 `true`）

当 `enabled=false` 时：

- 该 output MUST 被视为静态禁用
- 该 output MUST NOT 参与 required fields 解析与编译期依赖注入
- execution/output composition MUST NOT 为该 output 创建 sink，也 MUST NOT 写入任何内容

`where` 语义 MUST 保持不变：仍为 row-level filter/router，不应承担“禁用开关”的角色。

#### Scenario: disabled outputs do not create sinks
- **GIVEN** demand YAML 包含 output `name="foo"` 且 `enabled=false`
- **WHEN** 调用方编译并执行该 demand
- **THEN** 系统 MUST 不为 output `foo` 创建任何 sink
- **AND** 系统 MUST 不产生任何写入到 output `foo` 的副作用
