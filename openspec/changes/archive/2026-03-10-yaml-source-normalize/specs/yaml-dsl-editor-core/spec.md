## ADDED Requirements

### Requirement: 编辑器暴露源级 `normalize` 并提供与 canonical schema 一致的指引
系统 MUST 基于 canonical schema 在编辑器中暴露 `sources.*.normalize` 的补全、hover 与 schema-only 校验,并清楚区分它与字段级 `extract` 的边界。

#### Scenario: hover 说明 `normalize` 与 `extract` 的边界
- **WHEN** 用户在 `sources.*.normalize` 上查看 hover
- **THEN** 编辑器 MUST 展示其源级整体结果语义
- **AND** MUST 提示字段内部取值应使用字段级 `extract`
