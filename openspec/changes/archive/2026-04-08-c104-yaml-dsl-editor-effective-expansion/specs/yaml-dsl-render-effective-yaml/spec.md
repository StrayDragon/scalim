## ADDED Requirements

### Requirement: editor effective expansion MUST support outputs.fields flatten and YAML aliases

为支撑 editor 侧导航与补全,系统 MUST 提供静态的 effective expansion 视图,至少覆盖:

- YAML anchors/aliases 与 merge key 的展开（对当前打开文档以内存态文本为准）
- `outputs[*].fields` 的 nested list flatten 规则（与运行时/validator 口径一致）

#### Scenario: outputs.fields alias is expanded for navigation
- **GIVEN** YAML 使用 anchor 定义字段列表 `detail_fields: &detail_fields [a, b]`
- **AND** `outputs[0].fields` 使用 alias 引用 `- *detail_fields`
- **WHEN** editor 侧请求 outputs.fields 的 completion/definition
- **THEN** effective expansion MUST 将该 outputs.fields 视为展开后的有效列表（至少包含 `a`、`b`）
