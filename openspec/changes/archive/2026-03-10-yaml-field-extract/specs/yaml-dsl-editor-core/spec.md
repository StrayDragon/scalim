## ADDED Requirements

### Requirement: 编辑器暴露与 canonical schema 语义一致的 `extract`
系统 MUST 基于 canonical schema 在编辑器中暴露 `extract` 的补全、hover 与 schema-only 校验,并保持前端文案与主仓库 schema 一致。

#### Scenario: hover 展示 `extract` 的 current-row-relative 解释
- **WHEN** 用户在 `sources.*.fields.*.extract` 或 `main_source.fields.*.extract` 上查看 hover
- **THEN** 编辑器 MUST 展示“相对当前 row value 解析”的说明
- **AND** MUST 展示 `CustomerMark.clearn_reason_level` / `"[1].x"` / `'["a.b"]'` 之类的最小示例(明确为字符串,避免 YAML 歧义)
