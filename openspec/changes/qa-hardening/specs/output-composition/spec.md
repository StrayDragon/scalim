## ADDED Requirements

### Requirement: meta/audit error 记录默认不泄露敏感异常信息
当输出组合启用 meta/audit(例如 workbook 内的 Meta/Audit sheet)时,系统 MUST 默认避免将异常的原始 `error_message` 直接写入输出文件.

系统 MUST 至少满足以下行为:
- meta/audit MUST 记录 `error_type`
- meta/audit 的 `error_message` MUST 默认为安全摘要(例如空/占位/截断预览),不得包含多行与过长文本
- meta/audit SHOULD 记录稳定的 `error_message_hash`(用于对拍与聚类)
- 系统 MUST 提供显式开关以允许在“可信环境排障”时写入完整 `error_message`

#### Scenario: 默认仅写安全摘要
- **GIVEN** 派生输出(或某个输出目标)在运行中抛出异常且 error_message 含敏感片段(例如 token/SQL/URL)
- **WHEN** 输出组合启用 meta/audit
- **THEN** meta/audit MUST 记录该输出目标的 `error_type`
- **AND** meta/audit MUST NOT 写入原样 `error_message`
- **AND** meta/audit SHOULD 提供 `error_message_hash` 以便聚类/对拍

#### Scenario: 显式开启后允许写完整 message
- **GIVEN** 运行配置显式启用“落完整 error_message”
- **WHEN** 某个输出目标失败并产生异常 message
- **THEN** meta/audit MAY 写入完整 `error_message`
