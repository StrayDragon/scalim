# output-composition Specification

## MODIFIED Requirements

### Requirement: meta/audit error 记录默认不泄露敏感异常信息
当输出组合启用 meta/audit(例如 workbook 内的 Meta/Audit sheet)时,系统 MUST 默认避免将异常的原始 `error_message` 直接写入输出文件.

系统 MUST 至少满足以下行为:
- meta/audit MUST 记录 `error_type`
- meta/audit 的 `error_message` MUST 默认为安全摘要(例如空/占位/截断预览),不得包含多行与过长文本
- meta/audit SHOULD 记录稳定的 `error_message_hash`(用于对拍与聚类)
- 系统 MUST 提供显式开关以允许在“可信环境排障”时写入完整 `error_message`
  - 该开关 MUST 由 Python/CLI runtime entrypoints 控制
  - demand YAML stable authoring surface MUST NOT 提供该字段

#### Scenario: 默认仅写安全摘要
- **GIVEN** 派生输出(或某个输出目标)在运行中抛出异常且 error_message 含敏感片段(例如 token/SQL/URL)
- **WHEN** 输出组合启用 meta/audit
- **THEN** meta/audit MUST 记录该输出目标的 `error_type`
- **AND** meta/audit MUST NOT 写入原样 `error_message`
- **AND** meta/audit SHOULD 提供 `error_message_hash` 以便聚类/对拍

#### Scenario: 显式开启后允许写完整 message
- **GIVEN** 运行配置显式启用 `include_full_error_message=true`
- **WHEN** 某个输出目标失败并产生异常 message
- **THEN** meta/audit MAY 写入完整 `error_message`

### Requirement: effective header-name validation MUST follow unified write semantics
系统 MUST 在输出编译阶段按统一 `write` 语义判断是否需要启用“有效显示名唯一”校验。

并且该校验 MUST 由 runtime policy 开关 `validate_unique_field_names` 控制:
- 默认启用(未显式配置时等价 `true`)
- 当其为 `false` 时,系统 MUST 跳过该校验
- 该开关 MUST 由 Python/CLI runtime entrypoints 控制,而不是 demand YAML stable authoring 字段

#### Scenario: duplicate display names are rejected when validate_unique_field_names is enabled
- **GIVEN** 某 file output 会输出表头
- **AND** `write.header_fields_output_by=name`
- **AND** `validate_unique_field_names=true`
- **WHEN** 两个字段的 effective display name 相同
- **THEN** 编译 MUST fail-fast

#### Scenario: duplicate display names are allowed when validate_unique_field_names is disabled
- **GIVEN** 某 file output 会输出表头
- **AND** `write.header_fields_output_by=name`
- **AND** `validate_unique_field_names=false`
- **WHEN** 两个字段的 effective display name 相同
- **THEN** 编译 MUST NOT fail-fast on this check

