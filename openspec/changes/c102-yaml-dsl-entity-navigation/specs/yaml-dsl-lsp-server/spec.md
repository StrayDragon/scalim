## ADDED Requirements

### Requirement: YAML entity id references MUST support definition/completion/hover (single-file)

对同一 YAML 文件内的实体 ID 引用（例如 `fields.*.source`、`fields.*.relation`、`relations.*.steps[*].from/to`）,LSP server MUST 提供：

- definition：跳转到被引用实体的声明点（缺失时返回空并给出可诊断提示）
- completion：补全当前文件内已声明的可用实体 ID
- hover：展示被引用实体的只读摘要信息（静态，无副作用）

#### Scenario: fields.*.source can go to definition
- **GIVEN** YAML 声明 `sources.customers: ...`
- **AND** 某字段引用 `fields.customer_segment.source: customers`
- **WHEN** 用户在 `customers` 上触发 `textDocument/definition`
- **THEN** server MUST 跳转到 `sources.customers` 的 key 位置

#### Scenario: unknown entity id does not crash and provides a hint diagnostic
- **GIVEN** 某字段引用 `fields.x.source: not_exist`
- **WHEN** 用户触发 definition/hover/completion
- **THEN** server MUST 返回空结果（无 locations / 无 hover）
- **AND** MUST 提供 hint 级 diagnostic（例如 “Unknown source id: not_exist”）
