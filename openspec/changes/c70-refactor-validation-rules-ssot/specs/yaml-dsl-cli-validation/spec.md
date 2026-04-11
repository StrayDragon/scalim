# yaml-dsl-cli-validation (delta) Specification

## ADDED Requirements

### Requirement: YAML validation contracts MUST be centralized as SSOT across entrypoints

对于 YAML DSL 的稳定输入契约规则（例如 Excel `sheet_name` 校验、`outputs[*].name` 命名规则），系统 MUST 将其集中为单一 SSOT 实现，并在所有入口复用，以避免语义漂移：

- workflow compile、runtime compile、internal parsers 与 CLI validate MUST 复用同一套校验规则实现
- 对同一非法输入，不同入口 MUST 给出一致的接受/拒绝结果
- 错误信息 MUST 使用单一模板并包含一致的关键字段（至少包含逻辑 path、失败原因与可行动修复建议），以便 CLI/LSP 稳定定位与文档治理

#### Scenario: invalid sheet_name fails consistently across workflow and runtime compile
- **GIVEN** 用户提供一个非法的 Excel sheet_name（例如空值/超长/包含非法字符）
- **WHEN** 分别通过 workflow compile 与 runtime compile 入口进行校验
- **THEN** 两个入口 MUST 均 fail-fast
- **AND** 诊断信息 MUST 指向同一逻辑 path 并表达一致的失败原因

#### Scenario: invalid output name fails consistently across parsers
- **GIVEN** 用户提供一个不满足命名规则的 `outputs[*].name`
- **WHEN** 通过 internal parser 与 CLI validate 入口进行校验
- **THEN** 两个入口 MUST 给出一致的失败结论与关键诊断字段
