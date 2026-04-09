# yaml-dsl-editor-semantics-core Specification (Delta)

## ADDED Requirements

### Requirement: Editor semantics core MUST extract field-id tokens from `call_by` kwargs value positions
系统 MUST 扩展光标抽取能力，使其能在 `call_by` 的参数段（`(...)`）内识别 kwargs 的 `=` **右侧** field-id token，并用于 editor/LSP 语义能力。

覆盖 callsite 至少包括：
- `fields.*.call_by`
- `outputs[*].aggregate.fields.*.call_by`
- builtin callable：`call_by: "^<id>(...)"`（head 为 builtin id）

抽取必须满足：

- 抽取 MUST 仅对 `=` 右侧生效；`=` 左侧 kwargs 名称 MUST NOT 被当作 field-id
- token 抽取 MUST 返回精确 range（仅覆盖 token 本身）
- 当值为空（例如 `x=` 或 `x= `）且用户触发 completion 时，抽取结果 MUST 能提供稳定的 value_range（用于 completion）
- 解析失败 MUST 降级为空结果 + warnings（不得抛出未捕获异常）

#### Scenario: cursor on kwargs value token yields extracted field reference
- **GIVEN** YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
- **WHEN** 光标位于 `a` 上并触发 hover/definition
- **THEN** 抽取结果 MUST 将 token `a` 解析为字段引用
- **AND** MUST 返回仅覆盖 `a` 的 range

#### Scenario: cursor on kwargs name yields empty field extraction
- **GIVEN** YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
- **WHEN** 光标位于 `x` 上并触发 hover/definition
- **THEN** 系统 MUST NOT 将 `x` 解析为字段引用
- **AND** MUST 返回空结果（允许包含 warnings）
